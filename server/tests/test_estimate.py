"""The project estimate: credits still to spend, stage by stage."""

from tests.helpers import assert_hidden, assert_no_dollars
from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture


def _stages(editor, project):
    body = editor.get(f"/projects/{project}/estimate").json()
    return {s["stage"]: (s["done"], s["credits"]) for s in body["stages"]}, body


def test_estimate_follows_the_project(app, db, owner, editor, outsider, setup):  # noqa: F811
    project = setup["project"]  # 30 s planned; a script exists
    stages, body = _stages(editor, project)
    assert stages["script"] == (True, 0)
    assert stages["breakdown"] == (False, 3)  # one Claude call (write-claude rate)
    assert stages["storyboard"] == (False, 3 + 4 * 0.33)  # 30 s / 8 s ≈ 4 clips, 4 stills
    assert stages["clips"] == (False, 30)  # 30 s at 480p, 1 credit a second
    assert stages["video"] == (False, 0)  # free
    assert body["remaining_credits"] == round(3 + 3 + 1.32 + 3 + 30, 2)
    assert body["budget_credits"] == 60

    editor.post(f"/projects/{project}/breakdown")
    _run(app, db, FakeClaude(BREAKDOWN))  # one 5 s clip
    stages, body = _stages(editor, project)
    assert stages["breakdown"] == (True, 0)
    assert stages["storyboard"] == (False, 3 + 0.33)
    assert stages["clips"] == (False, 5)
    assert body["used_credits"] > 0

    assert_hidden(outsider, [("GET", f"/projects/{project}/estimate")])
    assert_no_dollars(editor, [f"/projects/{project}/estimate"])
