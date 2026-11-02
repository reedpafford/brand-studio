"""Every take with speech is asked for in American English (Reed's batch 4, the Director): the
clip prompt says it itself; a take built in code (a freestyle's one clip, a prompt without the
line) gets the same line, once."""

from app.clip_takes import ENGLISH, in_english
from tests.test_freestyles import HOUSE, SCRIPT


def test_a_take_says_american_english_once():
    said = "Language: every spoken line is in American English."
    told = f'References: [Image1] is Mia.\n{said}\nMIA: "Hi."'
    assert in_english(told) == told  # the clip prompt's own line: never twice
    bare = 'References: [Image1] is Mia.\nMIA: "Hi."'
    assert in_english(bare).splitlines()[1] == ENGLISH and "American English" in ENGLISH


def test_a_freestyles_one_clip_is_asked_in_american_english(owner, db):
    from app.models.jobs import Job

    owner.post("/freestyles", json={**HOUSE, "text": SCRIPT})
    (job,) = db.query(Job).all()
    assert job.input["input"]["prompt"].count("American English") == 1
