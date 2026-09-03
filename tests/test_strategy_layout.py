import ast
from pathlib import Path


def test_product_modules_define_at_most_one_top_level_class():
    root = Path(__file__).parents[1] / "gentians"
    violations = {}
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
        if len(classes) > 1:
            violations[str(path.relative_to(root))] = classes
    assert violations == {}


def test_hypothesis_plumbing_does_not_import_evolution():
    root = Path(__file__).parents[1] / "gentians" / "hypotheses"
    offenders = set()
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.split(".", 1)[0] in {"evolution", "gentians"}
                and (
                    node.module.startswith("evolution")
                    or node.module.startswith("gentians.evolution")
                )
            )
            or (
                isinstance(node, ast.Import)
                and any(
                    name.name.startswith("gentians.evolution") for name in node.names
                )
            )
            for node in ast.walk(tree)
        ):
            offenders.add(path.name)
    assert offenders == set()


def test_shared_evaluation_does_not_import_evolution():
    root = Path(__file__).parents[1] / "gentians" / "evaluation"
    offenders = set()
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and (
                node.module.startswith("evolution")
                or node.module.startswith("gentians.evolution")
            )
            for node in ast.walk(tree)
        ):
            offenders.add(path.name)
    assert offenders == set()
