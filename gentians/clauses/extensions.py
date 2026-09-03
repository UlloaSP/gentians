import re
from itertools import product


from ..language.asp import (
    Predicate,
    fragment_atoms,
    render_program,
)
from ..language.ir.inductive_task import InductiveTask
from .clause_space import ClauseSpace
from .task_analysis import _has_variable, _is_variable

def _numeric_domain_values(task: InductiveTask) -> set[int]:
    fragments = [*render_program(task.background)]
    for example in [*task.positive_examples, *task.negative_examples]:
        fragments.extend(
            [example.included_text, example.excluded_text, example.context_text]
        )
    constants = _numeric_constants(fragments)
    values = set(constants.values())
    for fragment in fragments:
        for start, end in re.findall(r"(-?\d+)\.\.([A-Za-z_]\w*|-?\d+)", fragment):
            if end.lstrip("-").isdigit():
                end_value = int(end)
            elif end in constants:
                end_value = constants[end]
            else:
                continue
            start_value = int(start)
            if abs(end_value - start_value) <= 10000:
                step = 1 if start_value <= end_value else -1
                values.update(range(start_value, end_value + step, step))
        values.update(
            int(value) for value in re.findall(r"(?<![\w-])-?\d+(?![\w])", fragment)
        )
    return values


def _numeric_constants(fragments: list[str]) -> dict[str, int]:
    constants: dict[str, int] = {}
    for fragment in fragments:
        for name, value in re.findall(
            r"#const\s+([A-Za-z_]\w*)\s*=\s*(-?\d+)\s*\.", fragment
        ):
            constants[name] = int(value)
    return constants


def _closed_world_extensions(
    fragments: list[str],
) -> dict[Predicate, set[tuple[str, ...]]]:
    extensions: dict[Predicate, set[tuple[str, ...]]] = {}
    constants = _numeric_constants(fragments)
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            if any(_has_variable(argument) for argument in arguments):
                continue
            key = (name, len(arguments))
            for values in _expand_ground_arguments(arguments, constants):
                extensions.setdefault(key, set()).add(values)
    _derive_closed_world_extensions(fragments, extensions)
    return extensions


def _derive_closed_world_extensions(
    fragments: list[str],
    extensions: dict[Predicate, set[tuple[str, ...]]],
    limit: int = 10000,
) -> None:
    changed = True
    while changed:
        changed = False
        for fragment in fragments:
            derived = _derive_closed_world_clause(fragment, extensions, limit)
            for predicate, tuples in derived.items():
                current = extensions.setdefault(predicate, set())
                if len(current) + len(tuples - current) > limit:
                    continue
                before = len(current)
                current.update(tuples)
                changed |= len(current) != before


def _derive_closed_world_clause(
    clause: str,
    extensions: dict[Predicate, set[tuple[str, ...]]],
    limit: int,
) -> dict[Predicate, set[tuple[str, ...]]]:
    text = clause.strip()
    if not text.endswith(".") or ":-" not in text or text.startswith("#"):
        return {}
    head_text, body_text = text[:-1].split(":-", 1)
    head = _simple_atom(head_text.strip())
    if head is None or any(not _is_variable(argument) for argument in head[1]):
        return {}
    positive: list[tuple[str, tuple[str, ...]]] = []
    negative: list[tuple[str, tuple[str, ...]]] = []
    for literal in _split_top_level(body_text):
        if literal.startswith("not "):
            atom = _simple_atom(literal[4:].strip())
            if atom is None:
                return {}
            negative.append(atom)
        else:
            atom = _simple_atom(literal)
            if atom is None:
                return {}
            positive.append(atom)
    if not positive or len(negative) > 1:
        return {}
    if negative and (negative[0][0], len(negative[0][1])) not in extensions:
        return {}
    assignments = [{}]
    for name, arguments in positive:
        tuples = extensions.get((name, len(arguments)))
        if tuples is None:
            return {}
        next_assignments = []
        for assignment in assignments:
            for values in tuples:
                merged = _merge_assignment(assignment, arguments, values)
                if merged is not None:
                    next_assignments.append(merged)
                    if len(next_assignments) > limit:
                        return {}
        assignments = next_assignments
    tuples: set[tuple[str, ...]] = set()
    for assignment in assignments:
        if negative and _negative_atom_holds(negative[0], assignment, extensions):
            continue
        try:
            tuples.add(tuple(assignment[argument] for argument in head[1]))
        except KeyError:
            return {}
    return {(head[0], len(head[1])): tuples}


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


def _simple_atom(text: str) -> tuple[str, tuple[str, ...]] | None:
    match = re.fullmatch(r"(-?[a-z][A-Za-z0-9_]*)\((.*)\)", text)
    if not match:
        return None
    return match.group(1), tuple(
        part.strip() for part in _split_top_level(match.group(2))
    )


def _merge_assignment(
    assignment: dict[str, str],
    arguments: tuple[str, ...],
    values: tuple[str, ...],
) -> dict[str, str] | None:
    merged = dict(assignment)
    for argument, value in zip(arguments, values):
        if _is_variable(argument):
            if argument in merged and merged[argument] != value:
                return None
            merged[argument] = value
        elif argument != value:
            return None
    return merged


def _negative_atom_holds(
    atom: tuple[str, tuple[str, ...]],
    assignment: dict[str, str],
    extensions: dict[Predicate, set[tuple[str, ...]]],
) -> bool:
    name, arguments = atom
    values: list[str] = []
    for argument in arguments:
        if _is_variable(argument):
            if argument not in assignment:
                return False
            values.append(assignment[argument])
        else:
            values.append(argument)
    return tuple(values) in extensions.get((name, len(arguments)), set())


def _expand_ground_arguments(
    arguments: tuple[str, ...],
    constants: dict[str, int],
    limit: int = 10000,
) -> list[tuple[str, ...]]:
    domains: list[list[str]] = []
    size = 1
    for argument in arguments:
        values = _expand_ground_argument(argument, constants)
        if values is None:
            return []
        size *= len(values)
        if size > limit:
            return []
        domains.append(values)
    return [tuple(values) for values in product(*domains)]


def _expand_ground_argument(
    argument: str, constants: dict[str, int]
) -> list[str] | None:
    text = argument.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    match = re.fullmatch(r"(-?\d+)\.\.([A-Za-z_]\w*|-?\d+)", text)
    if not match:
        if ".." in text:
            return None
        return [argument]
    start = int(match.group(1))
    end_text = match.group(2)
    if end_text.lstrip("-").isdigit():
        end = int(end_text)
    elif end_text in constants:
        end = constants[end_text]
    else:
        return None
    step = 1 if start <= end else -1
    return [str(value) for value in range(start, end + step, step)]


def _defined_predicates(fragments: list[str]) -> set[Predicate]:
    defined: set[Predicate] = set()
    clauses = [
        fragment
        for fragment in fragments
        if fragment.strip().endswith(".") and not fragment.lstrip().startswith("#")
    ]
    for entry in ClauseSpace.from_clauses(clauses).entries:
        defined.update(entry.heads)
    return defined


def _type_domains(
    fragments: list[str],
    predicate_arg_types: dict[tuple[str, int, int], str],
) -> dict[str, set[str]]:
    domains: dict[str, set[str]] = {}
    constants = _numeric_constants(fragments)
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            if any(_has_variable(argument) for argument in arguments):
                continue
            arity = len(arguments)
            for values in _expand_ground_arguments(arguments, constants):
                for index, value in enumerate(values):
                    arg_type = predicate_arg_types.get(
                        (name.removeprefix("-"), arity, index), "any"
                    )
                    if arg_type != "any":
                        domains.setdefault(arg_type, set()).add(value)
    return domains


def _universal_predicates(
    extensions: dict[Predicate, set[tuple[str, ...]]],
    predicate_arg_types: dict[tuple[str, int, int], str],
    type_domains: dict[str, set[str]],
    unary_type_domains: dict[str, dict[Predicate, set[str]]],
) -> set[Predicate]:
    universal: set[Predicate] = set()
    for predicate, tuples in extensions.items():
        domains: list[set[str]] = []
        for index in range(predicate[1]):
            arg_type = predicate_arg_types.get(
                (predicate[0].removeprefix("-"), predicate[1], index), "any"
            )
            domain = type_domains.get(arg_type, set())
            explicit_domain = set().union(
                *(
                    values
                    for source, values in unary_type_domains.get(arg_type, {}).items()
                    if source != predicate
                ),
                set(),
            )
            if arg_type == "any" or not domain or explicit_domain != domain:
                break
            domains.append(domain)
        else:
            size = 1
            for domain in domains:
                size *= len(domain)
            if size <= 10000 and tuples == set(product(*domains)):
                universal.add(predicate)
    return universal


def _unary_type_domains(
    fragments: list[str],
    predicate_arg_types: dict[tuple[str, int, int], str],
) -> dict[str, dict[Predicate, set[str]]]:
    domains: dict[str, dict[Predicate, set[str]]] = {}
    constants = _numeric_constants(fragments)
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            if len(arguments) != 1:
                continue
            value = arguments[0]
            if _has_variable(value):
                continue
            arg_type = predicate_arg_types.get((name.removeprefix("-"), 1, 0), "any")
            values = _expand_ground_argument(value, constants)
            if arg_type != "any" and values is not None:
                domains.setdefault(arg_type, {}).setdefault((name, 1), set()).update(
                    values
                )
    return domains
