"""Replay captured -s outputs, optionally rechecking the original executable.

Example (Linux):
  python -m tools.ilasp.validate_standalone --oracle '["./tools/ilasp/ILASP", "-s", "{task}"]'
For WSL, the command template also accepts {task_wsl}. Use --update only to
recapture expected outputs from the oracle; it never modifies the .las tasks.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import tempfile

from .standalone import Options, generate, parse_task
from .standalone.generator import _canonical

FIXTURE = Path(__file__).parents[2] / "tests/fixtures/ilasp-space.json"
EXTENSION_FIXTURE = FIXTURE.with_name("ilasp-space-extensions.json")
_FLAGS = {"max_body_literals": "-ml", "max_rule_length": "--max-rule-length",
          "max_wc_length": "--max-wc-length", "no_aggregates": "-na", "no_constraints": "-nc",
          "strict_types": "--strict-types", "override_default_sm": "--override-default-sm",
          "learn_heuristics": "--learn-heuristics"}


def weighted_rules(output: str) -> set[tuple[int, str]]:
    result = set()
    for line in output.splitlines():
        if not line.strip():
            continue
        cost, rule = line.split(" ~ ", 1)
        result.add((int(cost), _canonical(rule)))
    return result


def oracle_output(command: list[str], case: dict) -> str:
    with tempfile.TemporaryDirectory(prefix="ilasp-oracle-") as directory:
        path = Path(directory) / "task.las"
        path.write_text(case["source"], encoding="utf-8", newline="\n")
        wsl_path = "/mnt/" + path.drive[0].lower() + path.as_posix()[2:] if path.drive else str(path)
        args = [arg.format(task=str(path), task_wsl=wsl_path) for arg in command]
        args.extend(case.get("oracle_flags", ()))
        for key, value in case.get("options", {}).items():
            if isinstance(value, bool):
                if value:
                    args.append(_FLAGS[key])
            else:
                args.append(f"{_FLAGS[key]}={value}")
        result = subprocess.run(args, capture_output=True, text=True, timeout=120, check=True)
        if result.stderr.strip() != case.get("stderr", "").strip():
            raise RuntimeError(f"oracle wrote unexpected stderr: {result.stderr}")
        weighted_rules(result.stdout)  # Do not capture diagnostics as expected output.
        return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--oracle", type=json.loads, help="JSON command array, including -s and {task}")
    args = parser.parse_args()
    if args.update and not args.oracle:
        parser.error("--update requires --oracle")
    if args.oracle is not None and (not isinstance(args.oracle, list) or not args.oracle
                                    or not all(isinstance(arg, str) for arg in args.oracle)):
        parser.error("--oracle requires a nonempty JSON array of strings")
    fixtures = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in (FIXTURE, EXTENSION_FIXTURE)]
    total = 0
    count = 0
    for case in (case for _, fixture in fixtures for case in fixture["cases"]):
        options = Options(**case.get("options", {}))
        actual = {(e.cost, e.rule) for e in generate(parse_task(case["source"]), options)}
        output = oracle_output(args.oracle, case) if args.oracle else case["output"]
        expected = weighted_rules(output)
        if actual != expected:
            raise AssertionError({"case": case["name"], "missing": sorted(expected - actual)[:10],
                                  "extra": sorted(actual - expected)[:10], "options": asdict(options)})
        if args.update:
            case["output"] = output
        total += len(expected)
        count += 1
        print(f"{case['name']}: {len(expected)} OK", flush=True)
    if args.update:
        for path, fixture in fixtures:
            path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{count} cases, {total} distinct weighted entries: exact match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
