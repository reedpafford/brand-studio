"""No module in app/ defines the same top-level function or class twice: the later one would
silently replace the first (next, 7 Nov: two `_shown` helpers in app/director.py broke every
director turn)."""

import ast
from collections import Counter
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def test_no_module_defines_a_top_level_name_twice():
    twice = {}
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        names = Counter(n.name for n in tree.body if isinstance(
            n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))  # fmt: skip
        if dup := sorted(n for n, k in names.items() if k > 1):
            twice[str(path.relative_to(APP))] = dup
    assert not twice, twice
