"""Every speaker is a role at Assets, and nothing is drawn without a look for everyone in the
shot (Reed, 2026-10-27, "Marriage Rejection": only the bride was a role, so the video model
invented the groom). A free deploy repair adds the roles the cast read missed and puts each
in the shots it speaks on screen in; Storyboard and Clips wait for their looks, pointing to
Assets."""

import copy

from app import breakdown
from app.models.jobs import Job
from app.models.projects import Project
from app.prompts.schemas import Breakdown
from app.seed import repair_missing_roles
from tests.test_breakdown import BREAKDOWN
from tests.test_script_library import _make
from tests.test_unknown_cast import _look

TEXT = "INT. CHURCH — DAY\nNATE: Will you marry me?\nBRIDE: Hell no!\nNATE (V.O.): Day one."


def _video(owner, editor):
    """A published script whose cast read found only the bride; Nate speaks in shot 1.1 and
    over shot 1.2 (V.O.), and no shot shows him."""
    made = _make(owner, title="Marriage Rejection", text=TEXT)
    base = f"/scripts/{made['id']}"
    bride = owner.post(f"{base}/cast", json={"role": "Bride"}).json()[0]["id"]
    bd = copy.deepcopy(BREAKDOWN)
    one, two = bd["scenes"][0]["shots"]
    one.update(script_lines=[2], speaker="Nate", line="Will you marry me?", character_ids=[])
    two.update(script_lines=[3, 4], speaker="Nate", line="Day one.",
               character_ids=[f"slot:{bride}"])  # fmt: skip
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return base, editor.post(f"{base}/drafts/0/produce").json()["project_id"], bride


def _who(editor, pid):
    plan = editor.get(f"/projects/{pid}/breakdown").json()["breakdown"]
    return [s["character_ids"] for s in plan["scenes"][0]["shots"]]


def test_the_repair_adds_missed_speakers_and_shows_them_where_they_speak(owner, editor, db):
    base, pid, bride = _video(owner, editor)
    jobs = db.query(Job).count()
    said = repair_missing_roles(db)
    nate = next(s["id"] for s in owner.get(base).json()["cast"] if s["role"] == "Nate")
    shown = f"{db.get(Project, pid).name}: Shot 1.1 now shows Nate, who speaks in it."
    assert said == ["Marriage Rejection: added Nate to the cast", shown]
    assert _who(editor, pid) == [[f"slot:{nate}"], [f"slot:{bride}"]]  # not over his V.O.
    roles = [r["role"] for r in editor.get(f"/projects/{pid}/assets").json() if r["slot_id"]]
    assert roles == ["Bride", "Nate"]
    assert repair_missing_roles(db) == []  # once only
    assert db.query(Job).count() == jobs  # free: no model call


def test_storyboard_and_clips_wait_for_every_look_naming_them(owner, editor, db):
    _, pid, bride = _video(owner, editor)
    repair_missing_roles(db)
    nate = next(r["slot_id"] for r in editor.get(f"/projects/{pid}/assets").json()
                if r["role"] == "Nate")  # fmt: skip
    board, clips = f"/projects/{pid}/storyboard", f"/projects/{pid}/clips/prompts"
    for url in (board, clips):
        refused = editor.post(url, json={})
        assert refused.status_code == 409
        assert refused.json()["detail"] == (
            "Nate and Bride have no approved look yet. Approve them in Assets."
        )
    for slot, name in ((bride, "Bride look"), (nate, "Nate look")):
        look = {"library_item_id": _look(owner, db, name)}
        assert editor.put(f"/projects/{pid}/assets/slots/{slot}", json=look).status_code == 200
    assert editor.post(board, json={}).status_code == 201


def test_a_voiceover_or_off_screen_line_never_puts_the_speaker_in_the_shot(owner, editor, db):
    _, pid, _ = _video(owner, editor)
    repair_missing_roles(db)
    project = db.get(Project, pid)
    plan = Breakdown.model_validate(editor.get(f"/projects/{pid}/breakdown").json()["breakdown"])
    shot = plan.scenes[0].shots[0]
    shot.character_ids = []
    text = TEXT.replace("NATE: Will", "NATE (O.S.): Will")
    assert breakdown.show_speakers(db, project, plan, text) == []
    assert shot.character_ids == []
