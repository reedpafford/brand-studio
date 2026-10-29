"""Reed, DECISIONS #397/#399: nothing an editor reads sends them to Reed. Every message the
server can refuse with (an HTTPException's detail, or a constant passed as one) is checked
for his name. Owner-only routes' messages are covered too: wording that names Reed would
read oddly to the owner and confuse an editor who reaches the same route."""

import ast
import re
from pathlib import Path

from tests.helpers import approved_plan
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
        "An unnamed character that isn't part of this video",
        "shot 1.2: a place that isn't part of this video",
        "Advice: The Keep line doesn't name Mia",
        "Shot 1.1's screen Buy isn't attached",
    ]
    assert plain(said, called) == said  # said once, it stays the same
    assert not [p for p in said if IDS.search(p)]


def test_stored_checks_show_no_ids(app, db, editor, setup):  # noqa: F811
    """Frames, the breakdown and their kept advice, as people read them."""
    import copy

    from tests.test_breakdown import BREAKDOWN
    from tests.test_enhance import FakeClaude, _run

    url = f"/projects/{setup['project']}"
    bad = copy.deepcopy(BREAKDOWN)
    bad["scenes"][0]["shots"][0]["character_ids"] = ["char:999"]
    bad["scenes"][0]["shots"][0]["place_id"] = "place:7"
    saved = editor.put(f"{url}/breakdown", json=bad)  # never refused: taken out, as advice
    refused = " ".join(saved.json()["problems"])
    approved_plan(db, f"{url}")  # shots come from a plan (1b)
    editor.post(f"{url}/breakdown")
    _run(app, db, FakeClaude(bad))
    shown = editor.get(f"{url}/breakdown").json()["problems"]
    for text in [refused, *shown]:
        assert not IDS.search(text), text


def test_a_left_over_id_is_said_for_what_it_is(monkeypatch):
    """Reed saw "slot:28": whatever made a message, an id in it never reaches a person."""
    from app import advice
    from app.advice import said

    monkeypatch.setattr(advice, "LOOKUP", None)  # nothing to look it up in: what it is

    assert said("c2: slot:28 has no look yet") == "A character has no look yet"
    assert said("Advice: screen:4 is shown twice") == "Advice: a screen is shown twice"
    assert said("Mia has no look yet") == "Mia has no look yet"  # plain stays the same
    assert said("") == ""


def _shown_fields():
    """Every response field a person reads a check, kept advice or note in."""
    import importlib
    import pkgutil

    from pydantic import BaseModel

    import app.routes

    out = []
    for mod in pkgutil.iter_modules(app.routes.__path__):
        module = importlib.import_module(f"app.routes.{mod.name}")
        for model in vars(module).values():
            if isinstance(model, type) and issubclass(model, BaseModel):
                out += [(model.__name__, name, f) for name, f in model.model_fields.items()
                        if name in ("problems", "kept", "error", "seen", "problem")
                        and model.__name__.endswith("Out")]  # fmt: skip
    return out


def test_every_shown_check_goes_through_said():
    fields = _shown_fields()
    assert len(fields) >= 12  # the scan really finds them
    assert [(m, n) for m, n, f in fields if not f.metadata] == []


def test_a_stored_id_is_never_shown_and_can_still_be_kept(app, db, editor, setup):  # noqa: F811
    from app.models.breakdowns import BreakdownVersion
    from tests.test_storyboard import _with_breakdown

    _with_breakdown(app, db, editor, setup)
    bd = db.query(BreakdownVersion).filter_by(project_id=setup["project"]).one()
    bd.problems = ["Advice: c1: slot:28 looks older than the role"]  # saved before
    db.commit()
    url = f"/projects/{setup['project']}/breakdown"
    shown = editor.get(url).json()["problems"]
    assert shown == ["Advice: A character looks older than the role"]  # slot 28 isn't there
    kept = editor.post(f"{url}/keep", json={"problem": shown[0]})
    assert kept.status_code == 200, kept.text
    assert kept.json()["kept"] == shown
    undone = editor.delete(f"{url}/keep", params={"problem": shown[0]})
    assert undone.json()["kept"] == []


def test_a_left_over_id_is_named_from_the_askers_workspace_only(
    app,
    db,
    editor,
    outsider,
    setup,  # noqa: F811
):
    """Reed: the character's name, not "a character": a role by its name, a look and a
    screen by theirs. QA on #517: never a name from another workspace."""
    from app.models.breakdowns import BreakdownVersion
    from app.models.script_library import ScriptCastSlot
    from tests.conftest import upload
    from tests.test_storyboard import _with_breakdown

    fomo = editor.get("/brands").json()[0]["id"]
    script = editor.post("/scripts", json={"brand_id": fomo, "title": "S", "text": "A: hi"})
    slot = ScriptCastSlot(script_id=script.json()["id"], role="Nate, the son")
    db.add(slot)
    db.commit()
    mia = editor.post(
        "/library/character", json={"name": "Mia", "image_file_ids": [upload(editor)]}
    ).json()["id"]
    rival = outsider.post(
        "/library/character", json={"name": "Secret Rival", "image_file_ids": [upload(outsider)]}
    ).json()["id"]
    _with_breakdown(app, db, editor, setup)
    bd = db.query(BreakdownVersion).filter_by(project_id=setup["project"]).one()
    text = (f"Advice: c1: slot:{slot.id} and char:{mia} share screen:{setup['screen']}; "
            f"char:{rival} and char:99999 left")  # fmt: skip
    bd.problems = [text]  # saved before the plain-words work
    db.commit()
    (shown,) = editor.get(f"/projects/{setup['project']}/breakdown").json()["problems"]
    assert shown.startswith("Advice: Nate and Mia share ")
    assert "a screen" not in shown  # the brand screen by its own name
    assert shown.endswith("; a character and a character left")  # another workspace's: gone
    assert "Secret Rival" not in shown and not IDS.search(shown)


def test_no_message_sends_anyone_to_the_owner():
    """Rule 22 (c5, 2026-10-28): every failed job showed "Ask the owner for details." A message
    says what happened, whether anything was charged, and what to press next."""
    said = []
    for path in APP.rglob("*.py"):
        for n in ast.walk(ast.parse(path.read_text())):
            if isinstance(n, ast.Assign) and any(getattr(t, "id", "").isupper() for t in n.targets):
                said += [(path.name, s) for s in _strings(n.value) if "Ask the owner" in s]
    assert said == []
