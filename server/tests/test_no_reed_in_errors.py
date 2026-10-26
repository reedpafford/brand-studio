"""Reed, DECISIONS #397/#399: nothing an editor reads sends them to Reed. Every message the
server can refuse with (an HTTPException's detail, or a constant passed as one) is checked
for his name. Owner-only routes' messages are covered too: wording that names Reed would
read oddly to the owner and confuse an editor who reaches the same route."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _strings(node: ast.AST) -> list[str]:
    return [
        n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def _refusals() -> list[tuple[str, str]]:
    found = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text())
        constants = {
            t.id: _strings(n.value)
            for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            for t in n.targets
            if isinstance(t, ast.Name) and t.id.isupper()
        }
        for call in ast.walk(tree):
            if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "HTTPException":
                for arg in [*call.args, *(k.value for k in call.keywords)]:
                    texts = _strings(arg)
                    texts += [s for n in ast.walk(arg) if isinstance(n, ast.Name)
                              for s in constants.get(n.id, [])]  # fmt: skip
                    found += [(f"{path.name}:{call.lineno}", t) for t in texts]
    return found


def test_no_refusal_names_reed():
    refusals = _refusals()
    assert len(refusals) > 100  # the scan really finds the server's messages
    assert [r for r in refusals if "Reed" in r[1]] == []
