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


def test_breakdown_advice_can_be_kept(db, editor, setup, clip):  # noqa: F811
    url = f"/projects/{setup['project']}/breakdown"
    row = db.query(BreakdownVersion).order_by(BreakdownVersion.id.desc()).first()
    row.problems = [ADVICE]
    db.commit()
    assert editor.get(url).json()["kept"] == []
    assert editor.post(f"{url}/keep", json={"problem": ADVICE}).json()["kept"] == [ADVICE]
