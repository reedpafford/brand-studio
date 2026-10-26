"""Reed, DECISIONS #397/#399: nothing an editor reads sends them to Reed. Every message the
server can refuse with (an HTTPException's detail, or a constant passed as one) is checked
for his name. Owner-only routes' messages are covered too: wording that names Reed would
read oddly to the owner and confuse an editor who reaches the same route."""

import ast
import re
from pathlib import Path

from tests.test_enhance import setup  # noqa: F401 - fixture

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


# Ids people never read (Reed's live test: "c3: char:3 in the shot without a sheet").
IDS = re.compile(r"\b(char|slot|place|prop|screen|frame|voice):\w|(^|: )c\d+: ")
FILLED = re.compile(r"^(ref|r|c|i|sid|asset|screen|missing)$|ref\[|clip_id|reference_ids")


def _filled_in() -> list[tuple[str, str]]:
    """What a refusal fills in that could be an id (`{ref}`, `{clip.clip_id}`)."""
    found = []
    for path in APP.rglob("*.py"):
        for call in ast.walk(ast.parse(path.read_text())):
            if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "HTTPException":
                for arg in [*call.args, *(k.value for k in call.keywords)]:
                    for n in ast.walk(arg):
                        if isinstance(n, ast.FormattedValue):
                            found.append((f"{path.name}:{call.lineno}", ast.unparse(n.value)))
    return found


def test_no_refusal_shows_an_id():
    assert [r for r in _refusals() if IDS.search(r[1])] == []
    assert [f for f in _filled_in() if FILLED.search(f[1])] == []


def test_checks_are_said_with_names():
    from app.advice import plain

    called = {"char:3": "Mia", "screen:2": "Buy"}
    said = plain(
        [
            "c3: char:3 in the shot without a sheet",
            "c1: unknown reference char:9",
            "shot 1.2: unknown place:7",
            "Advice: c1: the Keep line doesn't name Mia",
            "c2: shot 1.1's screen screen:2 isn't attached",
        ],
        called,
    )
    assert said == [
        "Mia in the shot without a sheet",
        "A character that isn't part of this video",
        "shot 1.2: a place that isn't part of this video",
        "Advice: The Keep line doesn't name Mia",
        "Shot 1.1's screen Buy isn't attached",
    ]
    assert plain(said, called) == said  # said once, it stays the same
    assert not [p for p in said if IDS.search(p)]


def test_stored_checks_show_no_ids(app, db, editor, setup):  # noqa: F811
    """Frames, the breakdown and their kept advice, as people read them, also after the
    deploy step rewrites what was saved before."""
    import copy

    from app.models.breakdowns import BreakdownVersion
    from app.seed import plain_stored
    from tests.test_breakdown import BREAKDOWN
    from tests.test_enhance import FakeClaude, _run

    url = f"/projects/{setup['project']}"
    bad = copy.deepcopy(BREAKDOWN)
    bad["scenes"][0]["shots"][0]["character_ids"] = ["char:999"]
    bad["scenes"][0]["shots"][0]["place_id"] = "place:7"
    refused = editor.put(f"{url}/breakdown", json=bad).json()["detail"]
    editor.post(f"{url}/breakdown")
    _run(app, db, FakeClaude(bad))
    shown = editor.get(f"{url}/breakdown").json()["problems"]
    row = db.query(BreakdownVersion).filter_by(project_id=setup["project"]).one()
    row.problems, row.kept = [*row.problems, "c1: unknown char:999"], ["Advice: c1: char:999"]
    db.commit()
    assert plain_stored(db) >= 1 and plain_stored(db) == 0  # once, then nothing to do
    db.refresh(row)
    for text in [refused, *shown, *row.problems, *row.kept]:
        assert not IDS.search(text), text
