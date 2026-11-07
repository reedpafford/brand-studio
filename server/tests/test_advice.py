"""Advice never blocks: "Advice: …" problems let the step go on and can be kept anyway."""

from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from tests.test_clip_takes import clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture

ADVICE = "Advice: shot 2 runs a little long for its words"


def test_clip_advice_never_blocks_and_can_be_kept(db, editor, setup, clip):  # noqa: F811
    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    row = db.get(ProjectClip, clip["id"])
    row.problems = [ADVICE, "c1: shot 1.1's line isn't there once, word for word"]
    db.commit()
    assert editor.post(f"{url}/generate").status_code == 409  # the real problem still blocks
    assert editor.post(f"{url}/keep", json={"problem": row.problems[1]}).status_code == 409
    row.problems = [ADVICE]
    db.commit()
    kept = editor.post(f"{url}/keep", json={"problem": ADVICE}).json()
    assert kept["kept"] == [ADVICE] and kept["problems"] == [ADVICE]
    assert editor.post(f"{url}/keep", json={"problem": "Advice: gone"}).status_code == 404
    assert editor.post(f"{url}/generate").status_code == 201  # advice alone never blocks
    undone = editor.delete(f"{url}/keep", params={"problem": ADVICE}).json()
    assert undone["kept"] == [] and undone["problems"] == [ADVICE]


def test_breakdown_advice_can_be_kept(db, editor, setup, clip):  # noqa: F811
    url = f"/projects/{setup['project']}/breakdown"
    row = db.query(BreakdownVersion).order_by(BreakdownVersion.id.desc()).first()
    row.problems = [ADVICE]
    db.commit()
    assert editor.get(url).json()["kept"] == []
    assert editor.post(f"{url}/keep", json={"problem": ADVICE}).json()["kept"] == [ADVICE]
    assert editor.delete(f"{url}/keep", params={"problem": ADVICE}).json()["kept"] == []


def test_a_clips_problem_can_be_kept_anyway_once_its_free_fix_was_tried(db, editor, setup, clip):  # noqa: F811
    # one-click-fixes.md §5: past the free fix the card is never a dead end.
    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    problem = "c1: shot 1.1's line isn't there once, word for word"
    row = db.get(ProjectClip, clip["id"])
    row.problems = [problem]
    db.commit()
    early = editor.post(f"{url}/keep", json={"problem": problem})
    assert early.status_code == 409 and "free" in early.json()["detail"]  # the free fix first
    row.free_fix_used = True
    db.commit()
    kept = editor.post(f"{url}/keep", json={"problem": problem}).json()
    assert kept["kept"] == kept["problems"] and len(kept["kept"]) == 1  # still shown, as kept
    assert editor.post(f"{url}/generate").status_code == 201  # it no longer blocks the take
    undone = editor.delete(f"{url}/keep", params={"problem": problem}).json()
    assert undone["kept"] == []
    db.get(ProjectClip, clip["id"]).problems = [problem]
    db.commit()
    assert editor.post(f"{url}/generate").status_code == 409  # Undo: it blocks again


def test_our_ids_are_said_in_words_and_peoples_own_words_never_change():
    """MAIN's run, video 233: "(screen:3, the real UI)" in the treatment and the Plan tab. Our
    own kinds are named, or said for what they are; QA on #1409: people's words stay as typed
    (scores, times, a pasted address), and a person's message is never rewritten."""
    from app.advice import said, said_all
    from app.db import utcnow
    from app.routes.director import ThreadItem
    from app.routes.plan import LineOut

    assert said("A close-up (screen:3, the real UI).") == "A close-up (a screen, the real UI)."
    for words in ("home:2 away:1", "time:10s", "look:12", "https://example.com:8443/a",
                  "localhost:8443", "At 17:05."):  # fmt: skip
        assert said(words) == words, words
    beats = {"hook": "char:5 opens on screen:3", "beats": [{"id": 1, "picture": "frame:c2"}]}
    assert said_all(beats) == {"hook": "a character opens on a screen",
                               "beats": [{"id": 1, "picture": "a still"}]}  # fmt: skip
    told = {"beats": [{"picture": "(screen:3, the real UI)"}]}
    move = ThreadItem(id="s1", kind="move", at=utcnow(), who="Director", text="On screen:3.",
                      status="done", treatment=told)  # fmt: skip
    mine = ThreadItem(id="m1", kind="message", at=utcnow(), who="Reed",
                      text="Use screen:3 like at localhost:8443", status=None)  # fmt: skip
    line = LineOut(n=1, text="Rent's paid.", action="She holds up screen:3.", star=True)
    assert "screen:3" not in move.model_dump_json() + line.model_dump_json()
    assert mine.text == "Use screen:3 like at localhost:8443"  # a person's own words
