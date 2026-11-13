"""A spoken line too long for one clip (a paragraph of a presenter's monologue, a long
speech) is planned a sentence at a time (app/one_pass_assemble.units): the plan names each
sentence by its own number, code puts the exact words in, and every table that needs a
script line still gets the script's own. On the stand-ins."""

import pytest

from app import line_change, one_pass
from app.breakdown_fix import _sentences
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.one_pass_assemble import long_lines, units
from tests.test_one_pass_narrated import _delivered, _jobs, _run

MONOLOGUE = ("Your dog is not scratching because of fleas. It starts in the gut. When the gut "
             "is out of balance, the skin pays for it. Most owners treat the itch and miss the "
             "cause. Iron Paws puts real peanut butter and live cultures in one scoop. Mix it "
             "into the bowl once a day. In two weeks the scratching slows down. Get Iron Paws "
             "through the link below.")  # fmt: skip
SPEECH = ("Listen, Leo. I sold the car on Monday because Dr. Reyes said the engine was "
          "done. The buyer paid cash and drove it away before lunch. I put every dollar of it "
          "into the account you never check. Then I watched the number climb for three days "
          "straight. I did not tell you because you would have stopped me. Now look at the "
          "balance and tell me I was wrong.")  # fmt: skip
TALK = f"INT. KITCHEN - NIGHT\nMIA: {SPEECH}\nLEO: You were not wrong."


@pytest.fixture(autouse=True)
def _one_pass_on(monkeypatch):
    from app import guides
    from app.settings import get_settings

    monkeypatch.setattr(get_settings(), "one_pass", True)
    # the Dialogue tests here are made in Movie on a model of 15 s clips, whichever its guide names
    monkeypatch.setitem(guides.style("movie"), "video_model", "gemini-omni-1.2")


def _said(db, pid: int) -> list[str]:
    """Every line the clips' prompts say, in clip order."""
    import re

    rows = db.query(ProjectClip).filter_by(project_id=pid).order_by(ProjectClip.id)
    return [q for r in rows for x in r.prompt.splitlines() if x.startswith("Shot ")
            for q in re.findall(r'\): "(.+)"$', x)]  # fmt: skip


def test_a_long_line_is_numbered_a_sentence_a_row_and_its_words_never_change():
    assert long_lines(TALK, 15) == [2] and long_lines(TALK, 60) == []  # only when it can't fit
    rows, origin = units(TALK, [2])
    assert origin == [1, 2, 2, 2, 2, 2, 2, 2, 3] and rows.splitlines()[0] == "INT. KITCHEN - NIGHT"
    mine = [r.removeprefix("MIA: ") for r in rows.splitlines()[1:8]]
    assert " ".join(mine) == SPEECH and mine == _sentences(SPEECH)  # split, never re-typed
    assert mine[1].startswith("I sold the car on Monday because Dr. Reyes said")  # not at "Dr."
    assert units(TALK, []) == (TALK, [1, 2, 3])  # nothing long: the script as it is


def test_a_ugc_talkers_paragraph_is_said_a_sentence_at_a_time_across_its_clips(app, owner, db):
    pid = _delivered(app, owner, db, type="presenter", look="ugc", text=MONOLOGUE)
    (plan,) = _jobs(db, "one_pass")
    asked = plan.input["prompt"]
    assert "1| Your dog is not scratching because of fleas.\n2| It starts in the gut.\n" in asked
    assert plan.input["units"]["lines"] == [1] * 8  # eight rows, all of script line 1
    assert _said(db, pid) == _sentences(MONOLOGUE)  # every sentence once, in order, word for word
    talks = [r for r in db.query(ProjectClip).filter_by(project_id=pid) if '): "' in r.prompt]
    assert len(talks) > 1 and all(4 <= r.seconds <= 15 for r in talks)  # none past the model
    shots = owner.get(f"/projects/{pid}/breakdown").json()["breakdown"]["scenes"][0]["shots"]
    assert {n for s in shots for n in s["script_lines"]} == {1}  # the script's own line
    saved = one_pass.shooting_plan(db, db.get(Project, pid))
    assert saved["split"] == [1]  # kept with the plan: a note plans it by the same numbers


def test_a_dialogue_speech_too_long_for_one_clip_is_planned_by_its_sentences(app, owner, db):
    pid = _delivered(app, owner, db, type="dialogue", look="movie", text=TALK)
    assert len(SPEECH.split()) == 70
    assert _said(db, pid) == [*_sentences(SPEECH), "You were not wrong."]
    rows = db.query(ProjectClip).filter_by(project_id=pid).all()
    assert len(rows) > 1 and all(r.seconds <= 15 for r in rows)
    card = next(t["treatment"] for t in owner.get(f"/projects/{pid}/director").json()["thread"]
                if t.get("treatment"))  # fmt: skip
    assert {n for b in card["beats"] for n in b["lines"]} == {2, 3}  # the script's own lines


def _card(owner, pid: int, old: str, new: str) -> tuple[dict, dict]:
    said = owner.post(f"/projects/{pid}/director/messages",
                      json={"text": f"Change “{old}” to “{new}”"})  # fmt: skip
    assert said.status_code == 201, said.text
    asks = owner.get(f"/projects/{pid}/asks").json()
    (found,) = [a for a in asks if a["kind"] == "instead" and a["subject"] == old]
    return found, next(c for c in found["choices"] if c["do"] == line_change.DO)


def test_the_owner_changes_one_sentence_of_a_long_line_and_only_its_clip_is_remade(app, owner, db):
    pid = _delivered(app, owner, db, type="dialogue", look="movie", text=TALK)
    before = {r.clip_id: (r.prompt, db.query(ClipTake).filter_by(clip_id=r.id).count())
              for r in db.query(ProjectClip).filter_by(project_id=pid)}  # fmt: skip
    ask, change = _card(owner, pid, "on Monday", "on Tuesday")
    mine = [c for c, (prompt, _) in before.items() if "on Monday" in prompt]
    assert (
        len(mine) == 1 and f"Only clip {mine[0].removeprefix('c')} is made again" in change["why"]
    )
    assert not change["cannot"]
    yes = owner.post(f"/asks/{ask['id']}/answer", json={"how": "instead", "choice": change["key"]})
    assert yes.status_code == 200, yes.text
    _run(app, db, start=False)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    assert len(_jobs(db, "one_pass")) == 1  # the same plan, the new words by the same numbers
    after = {r.clip_id: (r.prompt, db.query(ClipTake).filter_by(clip_id=r.id).count())
             for r in db.query(ProjectClip).filter_by(project_id=pid)}  # fmt: skip
    assert {c for c in after if after[c] != before[c]} == set(mine)  # only that clip
    assert _said(db, pid) == [x.replace("Monday", "Tuesday") for x in _sentences(SPEECH)] + [
        "You were not wrong."]  # fmt: skip


def test_a_change_that_adds_a_sentence_to_a_long_line_is_refused_plainly(app, owner, db):
    pid = _delivered(app, owner, db, type="dialogue", look="movie", text=TALK)
    ask, change = _card(owner, pid, "drove it away before lunch", "drove it away. Before lunch")
    assert change["cannot"] == line_change.SENTENCES  # said on the card, before any press
    no = owner.post(f"/asks/{ask['id']}/answer", json={"how": "instead", "choice": change["key"]})
    assert no.status_code == 409 and no.json()["detail"] == line_change.SENTENCES
    assert len(_jobs(db, "one_pass")) == 1 and db.query(ClipTake).count() == db.query(
        ProjectClip).count()  # fmt: skip  # nothing changed, nothing made
