"""Long scripts (Reed, 10 Nov: a pasted script was cut at 5,000 characters, mid-word, "Share
this with ev"; his UGC scripts run 3-4 minutes, Movies longer). A script of up to 50,000
characters goes through whole, its price scales with it, and past the most it's refused in
plain words, never cut. All on the stand-ins (no paid call)."""

from app import asks, prompts
from app.models.asks import Ask
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.routes.freestyles import MAX_PROMPT
from tests.test_freestyle_dialogue import BODY, _run
from tests.test_script_library import _make


def _script(chars: int) -> str:
    """A two-hander about `chars` long, every line its own words (no quotes: the prompts
    escape them), ending on the line Reed's paste lost."""
    lines, n = [], 0
    while sum(len(x) + 1 for x in lines) < chars - 40:
        n += 1
        who = "MIA" if n % 2 else "LEO"
        lines.append(f"{who}: Line {n}, the market opened at nine and we were ready for it.")
    return "\n".join([*lines, "MIA: Share this with everyone you know."])


def test_a_20000_character_script_reaches_the_direction_card_word_for_word(app, owner, db):
    long, short = _script(20_000), _script(2_000)
    assert len(long) > 19_900
    priced = owner.post("/freestyles/estimate", json={**BODY, "text": long})
    assert priced.status_code == 200, priced.text  # a POST: it never rides in the address
    short_price = owner.post("/freestyles/estimate", json={**BODY, "text": short}).json()
    assert priced.json()["credits"] > short_price["credits"]  # the price scales with it
    r = owner.post("/freestyles", json={**BODY, "text": long})
    assert r.status_code == 201, r.text
    assert r.json()["up_to"] == priced.json()["credits"]  # the price shown is the one held
    fs = db.get(Freestyle, r.json()["id"])
    assert fs.chat[0]["text"] == long
    project = db.get(Project, fs.project_id, execution_options={"see_hidden": True})
    assert db.get(ScriptDraft, project.script_draft_id).text == long  # word for word
    _run(app, db, ticks=20, start=False)  # treatment, plan, breakdown, then the card (S3-02)
    db.query(Ask).filter_by(project_id=project.id, kind="start", state="open").one()  # the card
    told = db.query(Job).filter(Job.project_id == project.id).all()
    whole = {
        j.input["step"] for j in told if prompts.number_lines(long) in j.input.get("prompt", "")
    }
    assert whole == {"director", "treatment", "plan", "breakdown"}  # each reads all of it
    (card,) = [j for j in told if j.input.get(asks.START)]
    assert prompts.number_lines(long) in card.input["prompt"]  # the direction card's turn too


def test_past_the_most_a_script_is_refused_in_plain_words_never_cut(owner):
    over = "MIA: " + "go " * 16_666 + "go"  # 50,005 characters
    said = f"This script is {len(over):,} characters; the most is 50,000. Trim it or split it."
    for refused in (
        owner.post("/freestyles", json={**BODY, "text": over}),
        owner.post("/freestyles/estimate", json={**BODY, "text": over}),
        owner.post("/scripts", json={"brand_id": 1, "title": "Long", "text": over}),
        owner.put(f"/scripts/{_make(owner)['id']}/drafts/0", json={"text": over}),
    ):
        assert refused.status_code == 422
        assert refused.json()["detail"][0]["msg"] == said
    fits = owner.post("/scripts", json={"brand_id": 1, "title": "Long", "text": over[:50_000]})
    assert fits.status_code == 201, fits.text


def test_one_clip_too_long_for_its_prompt_says_to_pick_a_format(owner):
    words = "MIA: " + "go " * (MAX_PROMPT // 3)
    one = {**BODY, "type": "one_clip", "text": words}
    for refused in (owner.post("/freestyles/estimate", json=one),
                    owner.post("/freestyles", json=one)):  # fmt: skip
        assert refused.status_code == 422
        assert "Pick a format such as Dialogue for a longer script." in refused.json()["detail"]
