def clingo_stat(stats, *path: str) -> float:
    current = stats
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return 0.0
        current = current[key]
    return float(current) if isinstance(current, (int, float)) else 0.0


def ground_stats(ctl) -> dict[str, float]:
    stats = ctl.statistics
    atoms = max(
        clingo_stat(stats, "problem", "lp", "atoms"),
        clingo_stat(stats, "problem", "lpStep", "atoms"),
    )
    if not atoms:
        atoms = float(sum(1 for _ in ctl.symbolic_atoms))
    rules = max(
        clingo_stat(stats, "problem", "lp", "rules"),
        clingo_stat(stats, "problem", "lpStep", "rules"),
    )
    return {"atoms": atoms, "rules": rules}
