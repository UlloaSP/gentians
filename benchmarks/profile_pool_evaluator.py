"""Replay identical valid candidates through fresh and frozen-pool solvers.

Pools are unions of upcoming candidates, an optimistic reuse experiment with
known workloads. This measures evaluators, not time to learn a hypothesis.
"""

import argparse
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import clingo  # noqa: E402

from benchmarks.catalog import arguments_for  # noqa: E402
from gentians import timing  # noqa: E402
from gentians.clauses import ClauseSpace, generate_clause_space  # noqa: E402
from gentians.evaluation import create_epoch_pool_evaluator, create_evaluator  # noqa: E402
from gentians.gentians import task_from_arguments  # noqa: E402
from gentians.hypotheses import HypothesisGenerator  # noqa: E402


def candidate_sequence(hypotheses, seed, count):
    rng = random.Random(seed)
    candidates = []
    for _ in range(count * 100):
        genome = hypotheses.create(rng)
        if genome is not None:
            candidates.append(genome)
        if len(candidates) == count:
            return candidates
    raise ValueError(f"Only generated {len(candidates)} of {count} valid candidates")


def replay(task, config, hypotheses, genomes, epoch_size, pooled):
    timing.reset()
    timing.set_enabled(True)
    started = time.perf_counter()
    setup_seconds = 0.0
    evaluation_seconds = 0.0
    behaviors = []
    pool_sizes = []
    fresh = None
    if not pooled:
        setup_started = time.perf_counter()
        fresh = create_evaluator(task, config)
        setup_seconds += time.perf_counter() - setup_started
    for offset in range(0, len(genomes), epoch_size):
        batch = genomes[offset:offset + epoch_size]
        setup_started = time.perf_counter()
        if pooled:
            union = 0
            for genome in batch:
                union |= genome
            pool = ClauseSpace(
                entry for index, entry in enumerate(hypotheses.space.entries)
                if union & (1 << index)
            )
            pool_sizes.append(len(pool))
            evaluator = create_epoch_pool_evaluator(task, config, pool)
        else:
            assert fresh is not None
            evaluator = fresh
        setup_seconds += time.perf_counter() - setup_started
        evaluation_started = time.perf_counter()
        for genome in batch:
            behaviors.append(evaluator(hypotheses.program(genome)).behavior)
        evaluation_seconds += time.perf_counter() - evaluation_started
        del evaluator
    total_seconds = time.perf_counter() - started
    return behaviors, {
        "mode": "pooled" if pooled else "fresh",
        "total_seconds": total_seconds,
        "setup_seconds": setup_seconds,
        "evaluation_seconds": evaluation_seconds,
        "grounding_seconds": timing.recorded_seconds(f"{timing.current_phase()}.grounding") or 0.0,
        "solving_seconds": timing.recorded_seconds(f"{timing.current_phase()}.solving") or 0.0,
        "pool_sizes": pool_sizes,
        "ground_calls": len(pool_sizes) if pooled else len(genomes),
        "solve_calls": len(genomes),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", nargs="+", default=["5queens", "grandparent"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[1])
    parser.add_argument("--candidates", type=int, default=100)
    parser.add_argument("--epoch-size", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out-dir", type=Path, default=Path(".benchmarks/experiments/pool-evaluator"))
    args = parser.parse_args()
    if min(args.candidates, args.epoch_size, args.repeats) < 1:
        parser.error("candidates, epoch-size and repeats must be positive")
    # Detailed logging would contaminate this in-process replay measurement.
    for key in list(os.environ):
        if key.startswith("GENTIANS_") and key.endswith("_PATH"):
            os.environ.pop(key)
    records = []
    workloads = []
    for dataset in args.datasets:
        arguments = arguments_for(dataset)
        task = task_from_arguments(arguments)
        space = generate_clause_space(task, arguments)
        hypotheses = HypothesisGenerator(
            task, space, task.max_program_clauses or len(space)
        )
        for seed in args.seeds:
            genomes = candidate_sequence(hypotheses, seed, args.candidates)
            texts = [hypotheses.render(genome) for genome in genomes]
            digest = hashlib.sha256(json.dumps(texts).encode()).hexdigest()
            workloads.append({"dataset": dataset, "seed": seed, "sha256": digest,
                              "candidates": texts, "unique_candidates": len(set(genomes))})
            expected = None
            for repeat in range(args.repeats):
                for pooled in ((False, True) if repeat % 2 == 0 else (True, False)):
                    behaviors, metrics = replay(
                        task, arguments.evaluation, hypotheses, genomes, args.epoch_size, pooled
                    )
                    if expected is not None and behaviors != expected:
                        raise AssertionError(f"Coverage mismatch: {dataset}, seed {seed}")
                    expected = behaviors
                    records.append({"dataset": dataset, "seed": seed, "repeat": repeat,
                                    "workload_sha256": digest, **metrics})
            print(f"{dataset} seed={seed}: {args.candidates} candidates, coverage identical")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "python": platform.python_version(), "clingo": clingo.__version__,
        "platform": platform.platform(), "processor": platform.processor(),
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "worktree_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
        ).strip()),
        "epoch_size": args.epoch_size, "workloads": workloads, "records": records,
        "scope": "Evaluator replay; candidate generation excluded; upcoming-candidate union pools",
    }
    (args.out_dir / "replay.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
