import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .generator import Options, compile_task, generate
from .metarules import expand_metarule
from .task import read_task


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ILASP 4.4.1 candidate rules using only Python and Clingo.")
    parser.add_argument("task", type=Path)
    parser.add_argument("--emit-asp", action="store_true", help="emit the compiled generator instead of enumerating")
    parser.add_argument("--json", action="store_true", help="include attributes and metarule-selector metadata")
    parser.add_argument("--expand-metarules", action="store_true", help="JSON: include each selector's complete ASP program")
    parser.add_argument("-ml", "--max-body-literals", type=int, default=3)
    parser.add_argument("--max-rule-length", type=int, default=5)
    parser.add_argument("--max-wc-length", type=int, default=3)
    parser.add_argument("-na", "--no-aggregates", action="store_true")
    parser.add_argument("-nc", "--no-constraints", action="store_true")
    parser.add_argument("--strict-types", action="store_true")
    parser.add_argument("--override-default-sm", action="store_true")
    parser.add_argument("--learn-heuristics", action="store_true")
    parser.add_argument("-s", "--search-space", action="store_true", help="the default operation")
    parser.add_argument("-st", action="store_true", help="alias for --emit-asp")
    parser.add_argument("-mw", "--multi-wc", action="store_true", help="accepted; affects learning, not generation")
    parser.add_argument("--version", "-v", choices=("1", "2", "2i", "3", "4"), help="accepted; all versions share generation")
    parser.add_argument("--expand-sm", action="store_true", help="accepted; does not expand the native -s output")
    args = parser.parse_args()
    options = Options(args.max_body_literals, args.max_rule_length, args.max_wc_length,
                      args.no_aggregates, args.no_constraints, args.strict_types, args.override_default_sm,
                      args.learn_heuristics)
    try:
        task = read_task(args.task)
        if args.emit_asp or args.st:
            print(compile_task(task, options), end="")
        else:
            entries = generate(task, options)
            if args.json or args.expand_metarules:
                output = []
                for entry in entries:
                    item = asdict(entry)
                    if args.expand_metarules:
                        item["program"] = expand_metarule(task, entry)
                    output.append(item)
                print(json.dumps(output, ensure_ascii=False, indent=2))
            else:
                for entry in entries:
                    print(entry)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"ilasp-standalone: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
