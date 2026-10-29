"""A video's look in its picture prompts (flows ST2): its banned words repaired for you, free,
with Undo; a banned word in a quoted line is Advice, never changed; and the look's own fix
offered on a refused still or take and on an advisory finding."""

from app import clip_prompts, prompts, storyboard
from app.models.breakdowns import BreakdownVersion
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts import check
from tests.test_breakdown import BREAKDOWN
from tests.test_script_produce import _published


def test_a_clip_prompt_loses_the_looks_banned_words_but_never_a_spoken_line():
    prompt = 'Shot 1 (0-3s): Mia floating on a stage, smiling.\nAudio: Mia: "I was on a stage."'
    fixed, said = clip_prompts.reword(prompt, "zack-d")
    assert "resting in the world" in fixed and 'Mia: "I was on a stage."' in fixed
    assert "on a stage → in the world" in said and "floating → resting" in said
    assert clip_prompts.reword(prompt, "house") == (prompt, [])  # House bans neither


def test_a_still_is_fixed_for_the_look_with_undo_and_a_quoted_word_is_advice():
    after, note = storyboard.look_fixed("A man floating on a stage.", "zack-d", None)
    assert after == "A man resting in the world."
    assert note["before"] == "A man floating on a stage." and note["after"] == after
    assert note["note"].startswith("Fixed for the look: ") and note["look_fixed"]
    _, changed, advice = check.look_words('A sign reads "the stage is yours".', "zack-d")
    assert changed == [] and advice  # rule 19: what's quoted is never changed


def test_the_cards_show_the_fix_and_the_looks_next_step(owner, editor, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    video = f"/projects/{editor.post(f'{base}/drafts/0/produce').json()['project_id']}"
    pid = int(video.rsplit("/", 1)[1])
    db.get(Project, pid).look = "zack-d"
    bd = db.query(BreakdownVersion).filter_by(project_id=pid).one()
    after, note = storyboard.look_fixed("Mia floating on a stage.", "zack-d", None)
    db.add(StoryboardFrame(project_id=pid, breakdown_id=bd.id, clip_id="c1", shot_id="1.1",
                           prompt=after, change=note, problems=[storyboard.REFUSED]))  # fmt: skip
    db.commit()
    (frame,) = editor.get(f"{video}/storyboard").json()
    assert frame["look_fixed"] == {"fixed": note["look_fixed"], "before": note["before"],
                                   "after": after}  # fmt: skip
    assert frame["look_fix"] == prompts.look_fixes("zack-d")["refused"]


def test_an_advisory_finding_offers_the_looks_fix(owner, editor, db):
    from app import item_checks
    from app.models.checks import ItemCheck

    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    db.get(Project, pid).look = "zack-d"
    row = ItemCheck(project_id=pid, target="frame", target_id=1, status="done",
                    findings=[{"kind": "outfit", "role": "char:1", "text": "Her coat differs.",
                               "change_note": "keep the red coat"}])  # fmt: skip
    db.add(row)
    db.commit()
    (finding,) = item_checks.shown(db, row).findings
    assert finding.fix == prompts.look_fixes("zack-d")["outfit"]
