import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TaskStats:
    file: Path
    background_rules: int = 0
    facts: int = 0
    constraints: int = 0
    pos_examples: int = 0
    neg_examples: int = 0
    head_modes: int = 0
    body_modes: int = 0
    negative_body_modes: int = 0
    max_arity: int = 0
    has_numbers: bool = False
    has_comparison: bool = False
    repeated_predicates: bool = False
    predicate_counts: dict[str, int] | None = None


def split_args(args: str) -> list[str]:
    if not args.strip():
        return []

    parts = []
    depth = 0
    current = []
    for ch in args:
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        current.append(ch)

    if current:
        parts.append("".join(current).strip())
    return parts


def atom_name_arity(text: str) -> tuple[str, int] | None:
    text = text.strip()
    text = text.removeprefix("not ").strip()
    match = re.match(r"^([a-zA-Z_]\w*)\((.*)\)$", text)
    if not match:
        if re.match(r"^[a-zA-Z_]\w*$", text):
            return text, 0
        return None
    return match.group(1), len(split_args(match.group(2)))


def scan_task(path: Path) -> TaskStats:
    stats = TaskStats(file=path, predicate_counts={})
    comparison_re = re.compile(r"(<|>|<=|>=|=|!=)")
    number_re = re.compile(r"(?<![A-Za-z_])\d+(?![A-Za-z_])")
    modeh_re = re.compile(r"^#modeh\((\d+|\*),([a-zA-Z_]\w*),(\d+)\)\.$")
    modeb_re = re.compile(
        r"^#modeb\((\d+|\*),([a-zA-Z_]\w*),(\d+),(positive|negative)\)\.$"
    )

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue

        compact = line.replace(" ", "")

        if compact.startswith("#pos("):
            stats.pos_examples += 1
            stats.has_numbers = stats.has_numbers or bool(number_re.search(compact))
            continue
        if compact.startswith("#neg("):
            stats.neg_examples += 1
            stats.has_numbers = stats.has_numbers or bool(number_re.search(compact))
            continue

        mh = modeh_re.match(compact)
        if mh:
            stats.head_modes += 1
            stats.max_arity = max(stats.max_arity, int(mh.group(3)))
            continue

        mb = modeb_re.match(compact)
        if mb:
            stats.body_modes += 1
            stats.max_arity = max(stats.max_arity, int(mb.group(3)))
            if mb.group(4) == "negative":
                stats.negative_body_modes += 1
            continue

        stats.has_numbers = stats.has_numbers or bool(number_re.search(line))
        stats.has_comparison = stats.has_comparison or bool(comparison_re.search(line))

        if line.startswith(":-"):
            stats.constraints += 1
        elif ":-" in line:
            stats.background_rules += 1
        else:
            stats.facts += 1

        head = line.split(":-", 1)[0].strip().rstrip(".")
        atom = atom_name_arity(head)
        if atom:
            name, arity = atom
            stats.predicate_counts[name] = stats.predicate_counts.get(name, 0) + 1
            stats.max_arity = max(stats.max_arity, arity)

    stats.repeated_predicates = any(v >= 3 for v in stats.predicate_counts.values())
    return stats


def choose_flags(stats: TaskStats, preset: str) -> list[str]:
    examples = stats.pos_examples + stats.neg_examples
    body_modes = max(stats.body_modes, 1)
    head_modes = max(stats.head_modes, 1)

    variables = max(2, min(5, stats.max_arity + 1))
    depth = max(3, min(6, 1 + min(5, body_modes // 2 + 1)))
    clauses = max(2, min(6, head_modes + 2))
    samples = max(100, min(3000, body_modes * 100))
    pop_size = max(50, min(200, body_modes * 8))
    iterations_genetic = max(400, min(5000, clauses * body_modes * 80))
    iterations = max(2, min(10, max(1, examples) // 3))

    if preset == "easy":
        samples = max(100, samples // 2)
        pop_size = max(50, pop_size)
        iterations_genetic = max(300, iterations_genetic // 2)
        iterations = max(1, iterations // 2)
    elif preset == "exhaustive":
        depth = min(7, depth + 1)
        clauses = min(8, clauses + 2)
        samples = min(8000, samples * 3)
        pop_size = min(300, max(100, pop_size * 2))
        iterations_genetic = min(10000, iterations_genetic * 3)
        iterations = min(20, max(6, iterations * 2))

    flags = [
        "-f",
        str(stats.file),
        "-it",
        str(iterations),
        "-s",
        str(samples),
        "-p",
        str(pop_size),
        "-itg",
        str(iterations_genetic),
        "-c",
        str(clauses),
        "-d",
        str(depth),
        "-vars",
        str(variables),
        "-v",
        "1",
    ]

    if stats.head_modes == 0 or stats.body_modes == 0:
        flags.extend(["-alb=1"])

    if stats.has_comparison:
        flags.extend(["--comparison", "lt", "leq", "gt", "geq", "eq", "neq"])
    elif stats.has_numbers and preset == "exhaustive":
        flags.extend(["--comparison", "lt", "gt", "geq", "neq"])

    if stats.has_numbers and preset == "exhaustive":
        flags.extend(["--arithm", "add", "sub"])

    return flags


def explain(stats: TaskStats, flags: list[str]) -> None:
    print("Detected:")
    print(f"- file: {stats.file}")
    print(f"- facts: {stats.facts}")
    print(f"- background rules: {stats.background_rules}")
    print(f"- constraints: {stats.constraints}")
    print(f"- positive examples: {stats.pos_examples}")
    print(f"- negative examples: {stats.neg_examples}")
    print(f"- head modes: {stats.head_modes}")
    print(f"- body modes: {stats.body_modes}")
    print(f"- negative body modes: {stats.negative_body_modes}")
    print(f"- max arity: {stats.max_arity}")
    print(f"- numbers: {stats.has_numbers}")
    print(f"- comparisons in background: {stats.has_comparison}")
    print(f"- repeated predicates: {stats.repeated_predicates}")
    print()
    print("Chosen flags:")
    print(" ".join(flags))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Infer GENTIANS flags from task file and optionally run it."
    )
    parser.add_argument("file", help="Task file, e.g. pruebas3.txt")
    parser.add_argument(
        "--preset",
        choices=["easy", "balanced", "exhaustive"],
        default="balanced",
        help="Search budget preset.",
    )
    parser.add_argument(
        "--exe",
        default=r".\.venv\Scripts\gentians.exe",
        help="Path to gentians executable.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run command. Without this, only prints chosen config.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output file. Example: resultados_pruebas/auto.txt",
    )
    args = parser.parse_args()

    task_file = Path(args.file)
    if not task_file.exists():
        print(f"ERROR: file not found: {task_file}", file=sys.stderr)
        return 2

    stats = scan_task(task_file)
    flags = choose_flags(stats, args.preset)
    command = ["uv", "run", args.exe, *flags]

    explain(stats, flags)
    print()
    print("Command:")
    print(" ".join(command))

    if not args.run:
        return 0

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as handle:
            return subprocess.call(command, stdout=handle, stderr=subprocess.STDOUT)

    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
