"""Breakdown step with a mocked Claude (no paid calls)."""

import copy

from app import breakdown
from app.models.jobs import Job
from tests.helpers import assert_hidden, assert_no_dollars
from tests.test_enhance import SCRIPT, FakeClaude, _run, setup  # noqa: F401 - fixture


def _shot(id, lines, speaker, line, seconds):
    return {
        "id": id,
        "script_lines": lines,
        "speaker": speaker,
        "line": line,
        "action": "They argue.",
        "reaction": None,
        "camera": "Close-up, push in",
        "seconds": seconds,
        "character_ids": [],
        "place_id": None,
        "moment": None,
        "screen_ids": [],
    }


BREAKDOWN = {
    "hook": "Mom bursts in with the empty wallet.",
    "scenes": [
        {
            "id": 1,
            "heading": "INT. KITCHEN — MORNING",
            "look": "Cold morning light.",
            "shots": [
                _shot("1.1", [2, 3], "Mom", "Nate, where is all your money?", 2.5),
                _shot("1.2", [4], "Nate", "I bought the dip.", 1.5),
            ],
        }
    ],
    "clips": [{"id": "c1", "shot_ids": ["1.1", "1.2"], "seconds": 5, "seam": "End of scene."}],
}


def test_breakdown_made_checked_and_edited(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}/breakdown"
    assert editor.get(url).status_code == 204  # none yet: no content, not an error
    job = editor.post(url)
    assert job.status_code == 201 and job.json()["credits"] == 3
    assert editor.post(url).status_code == 409  # one at a time
    fake = FakeClaude(BREAKDOWN)
    _run(app, db, fake)
    assert db.get(Job, job.json()["id"]).status == "succeeded"
    sent = fake.requests[0]
    assert sent["max_tokens"] == breakdown.TOKENS
    message = sent["messages"][0]["content"]
    assert "<places>" in message and "<video_model>Seedance 2.5: 4–30 s" in message
    assert "3| MOM: Nate, where is all your money?" in message

    got = editor.get(url).json()
    # rule 18: the ending is the script's own, so a script not naming fomo last is fine
    assert (got["source"], got["stale"]) == ("claude", False)
    assert got["problems"] == []
    assert got["breakdown"]["clips"][0]["shot_ids"] == ["1.1", "1.2"]

    edited = copy.deepcopy(BREAKDOWN)
    edited["scenes"][0]["shots"].pop()
    edited["clips"][0]["shot_ids"] = ["1.1"]
    saved = editor.put(url, json=edited).json()
    assert saved["source"] == "edit" and "line 4 is in no shot" in saved["problems"]
    assert editor.get(url).json()["id"] == saved["id"]

    editor.put(f"/projects/{setup['project']}/script", json={"text": SCRIPT + "\nMOM: Fine."})
    assert editor.get(url).json()["stale"] is True


def test_breakdown_needs_a_script_switch_and_workspace(app, editor, outsider, setup):  # noqa: F811
    url = f"/projects/{setup['project']}/breakdown"
    assert_hidden(outsider, [("POST", url), ("GET", url), ("PUT", url, BREAKDOWN)])
    app.state.settings.generation_enabled = False
    try:
        assert editor.post(url).status_code == 503
    finally:
        app.state.settings.generation_enabled = True
    editor.post(url)
    assert_no_dollars(editor, [f"/projects/{setup['project']}"])


def test_each_line_gets_room_at_the_styles_pace_and_the_clips_keep_to_the_length(
    app,
    db,
    editor,
    setup,  # noqa: F811
):
    """Critique 276: Movie gave Granny's two sentences 2.8 s and Omni put the rest of her line
    on Maya's face; the plan ran 35 s for a 30 s brief. A line's shot gets its words at the
    style's pace and its pauses (free), and clips over the length asked for are written again
    once, what's left kept as Advice."""
    from app import guides
    from app.prompts import check
    from app.prompts.schemas import Breakdown

    assert (guides.pace("movie", "dialogue"), guides.pause("movie", "dialogue")) == ((2, 3), 0.6)
    assert guides.pace("house", "dialogue") == (3.5, 4.8) and not guides.pause("house", "dialogue")
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0].update(line="Oh honey, congratulations! When are you due?",
                                       seconds=2.8)  # fmt: skip
    bd["scenes"][0]["shots"][1]["seconds"] = 2.5
    bd["clips"][0]["seconds"] = 8  # a long wordless tail
    roomy, said = check.line_room(Breakdown.model_validate(bd), 3, 0.6)
    assert [s.seconds for s in roomy.scenes[0].shots] == [3.5, 2.5]  # 7 ÷ 3 + 2 × 0.6; never less
    assert said == ["Advice: Shots 1.1 got more time so each line has room at this style's pace."]
    assert check.planned_length(roomy, 8, 3, 0.6) == []  # within a tenth
    assert check.planned_length(roomy, 20, 3, 0.6) == []  # short: never padded
    assert not check.planned_length(roomy, 5, 3, 0.6)[0].startswith("Advice: ")  # over: a fix
    assert "lines alone need about 5 s" in check.planned_length(roomy, 2, 3, 0.6)[0]  # kept

    long = copy.deepcopy(BREAKDOWN)  # 40 s against the brief's 30 s
    long["clips"] = [{"id": "c1", "shot_ids": ["1.1"], "seconds": 20, "seam": "A look."},
                     {"id": "c2", "shot_ids": ["1.2"], "seconds": 20, "seam": "end"}]  # fmt: skip
    editor.post(f"/projects/{setup['project']}/breakdown")
    fake = FakeClaude(long)
    _run(app, db, fake)
    first, again = (r["messages"][0]["content"] for r in fake.requests)
    assert "<timing>\nSpeaking pace in this style: up to 4.8 words a second" in first
    assert "Length: about 30 s asked for, so the clips add up to 27–33 s." in first
    assert "the clips add up to 40 s, over the 30 s asked for" in again.split("<fix>")[1]
    got = editor.get(f"/projects/{setup['project']}/breakdown").json()
    assert any(p.startswith("Advice: the clips add up to 40 s") for p in got["problems"])
