"""ILASP execution backend for the shared experiment runner."""

import csv
import gzip
import os
import platform
import re
import subprocess
import time
from pathlib import Path

from benchmarks.catalog import arguments_for
from benchmarks.check_hypothesis import validate_run
from gentians.language.asp import parse_program

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE_PATTERNS = {
    field: re.compile(rf"^%% {label}\s+:\s+([0-9.]+)s$", re.MULTILINE)
    for field, label in (
        ("preprocessing_seconds", "Pre-processing"),
        ("hypothesis_space_seconds", "Hypothesis Space Generation"),
        ("conflict_analysis_seconds", "Conflict analysis"),
        ("counterexample_search_seconds", "Counterexample search"),
        ("hypothesis_search_seconds", "Hypothesis Search"),
        ("total_seconds", "Total"),
    )
}
RUN_FIELDS = ("dataset", "version", "run", "status", "returncode", "wall_seconds",
              *PHASE_PATTERNS, "success", "hypothesis_path", "validation_path", "stdout_path", "stderr_path")


def repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def task_path(experiment: dict, dataset: str) -> Path:
    return repo_path(experiment["tool_options"].get("task_dir", "benchmarks/ilasp")) / f"{dataset}.las"


def linux_path(path: Path) -> str:
    if platform.system() != "Windows":
        return str(path.resolve())
    drive, tail = os.path.splitdrive(str(path.resolve()))
    if not drive:
        raise ValueError(f"Expected a Windows path, got {path}")
    return f"/mnt/{drive[0].lower()}/{tail.lstrip('\\/').replace('\\', '/')}"


def build_command(experiment: dict, dataset: str) -> list[str]:
    options = experiment["tool_options"]
    command = []
    if platform.system() == "Windows":
        command = ["wsl"]
        if options.get("distro"):
            command.extend(("-d", options["distro"]))
        command.append("--")
    elif platform.system() != "Linux":
        raise ValueError("ILASP requires Linux or Windows with WSL")
    if runtime := options.get("python_runtime"):
        command.extend(("env", f"LD_LIBRARY_PATH={runtime}/lib/x86_64-linux-gnu", f"PYTHONHOME={runtime}"))
    executable = options.get("executable", "tools/ilasp/ILASP")
    if not executable.startswith("/"):
        executable = linux_path(repo_path(executable))
    command.extend(("timeout", "--signal=INT", "--kill-after=5s", f"{experiment['timeout_seconds']}s",
                    executable, f"--version={experiment['variant']}",
                    f"-ml={options['max_body_length'][dataset]}", linux_path(task_path(experiment, dataset))))
    return command


def extract_hypothesis(stdout: str, returncode: int | None) -> str | None:
    source = "\n".join(line for line in stdout.splitlines() if not line.lstrip().startswith("%"))
    if not source.strip() and (returncode != 0 or "%% Total" not in stdout):
        return None
    try:
        statements = parse_program(source)
    except (ValueError, RuntimeError):
        return None
    return "\n".join(map(str, statements)) + "\n"


def run_experiment(experiment: dict, output_dir: Path) -> int:
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    runs_path = output_dir / "runs.csv"
    if runs_path.exists():
        with runs_path.open(encoding="utf-8", newline="") as file:
            completed = {row["dataset"] for row in csv.DictReader(file)}
    else:
        completed = set()
    for index, dataset in enumerate(experiment["datasets"], 1):
        if dataset in completed:
            print(f"{experiment['id']}: {dataset}: cached", flush=True)
            continue
        stem = f"{dataset}_run_1"
        hypothesis_path = runs_dir / f"{stem}_hypothesis.lp"
        validation_path = runs_dir / f"{stem}_validation.json"
        for path in (hypothesis_path, validation_path):
            path.unlink(missing_ok=True)
            path.with_name(path.name + ".gz").unlink(missing_ok=True)
        command = build_command(experiment, dataset)
        print(f"[{index}/{len(experiment['datasets'])}] {experiment['method']} {dataset}", flush=True)
        started = time.perf_counter()
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=experiment["timeout_seconds"] + 10 if experiment["timeout_seconds"] else None,
                                    check=False)
            returncode, stdout, stderr = result.returncode, result.stdout, result.stderr
            status = "ok" if returncode == 0 else "timeout" if returncode in (9, 124, 137) else "failed"
        except subprocess.TimeoutExpired as error:
            returncode, status = None, "timeout"
            stdout = decode_output(error.stdout)
            stderr = decode_output(error.stderr)
        elapsed = time.perf_counter() - started
        hypothesis = extract_hypothesis(stdout, returncode)
        if hypothesis is not None:
            hypothesis_path.write_text(hypothesis, encoding="utf-8")
        validation = validate_run(Path(arguments_for(dataset).filename), hypothesis_path, validation_path,
                                  timeout_seconds=experiment["validation_timeout_seconds"],
                                  learner_task_path=task_path(experiment, dataset))
        row = {"dataset": dataset, "version": experiment["variant"], "run": 1, "status": status,
               "returncode": "" if returncode is None else returncode, "wall_seconds": f"{elapsed:.6f}",
               "success": validation["valid"] is True, "hypothesis_path": "", "validation_path": ""}
        for field, pattern in PHASE_PATTERNS.items():
            match = pattern.search(stdout)
            row[field] = match.group(1) if match else ""
        for field, suffix, content in (("stdout_path", ".out", stdout), ("stderr_path", ".err", stderr)):
            path = runs_dir / f"{stem}{suffix}.gz"
            with gzip.open(path, "wt", encoding="utf-8") as file:
                file.write(content)
            row[field] = str(path.relative_to(output_dir))
        for field, path in (("hypothesis_path", hypothesis_path), ("validation_path", validation_path)):
            if path.exists():
                compressed = path.with_name(path.name + ".gz")
                with gzip.open(compressed, "wb") as file:
                    file.write(path.read_bytes())
                path.unlink()
                row[field] = str(compressed.relative_to(output_dir))
        exists = runs_path.exists()
        with runs_path.open("a", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=RUN_FIELDS)
            if not exists:
                writer.writeheader()
            writer.writerow(row)
    return 0


def decode_output(value: str | bytes | None) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
