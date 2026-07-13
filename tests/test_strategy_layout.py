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
