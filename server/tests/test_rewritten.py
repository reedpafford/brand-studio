""" "Was:" marks on a reel-made script (reel-import.md §6): the rewritten lines and the reel's
original words, kept through edits until approval."""

from app import rewritten
from app.models.script_library import ScriptDraft
from tests.test_script_library import _make

REEL = ["Will you marry me?", "I bought 40 hoodies to resell.", "No."]
TEXT = "SCENE 1\nGROOM: Will you marry me?\nGROOM: I bought 40 shares of one coin.\nBRIDE: No."


def test_marks_pair_each_rewritten_line_with_the_reels_words():
    got = rewritten.marks(TEXT, ["I bought 40 shares of one coin."], REEL)
    assert got == [{"line_index": 2, "was": "I bought 40 hoodies to resell."}]
    assert rewritten.marks(TEXT, [], REEL) == []  # nothing rewritten, nothing marked


def test_marks_follow_their_lines_through_edits():
    mark = [{"line_index": 2, "was": "I bought 40 hoodies to resell."}]
    added = TEXT.replace("SCENE 1\n", "SCENE 1\nGroom kneels.\n")
    assert rewritten.follow(TEXT, added, mark)[0]["line_index"] == 3  # a line added above
    edited = TEXT.replace("one coin", "a meme coin")
    assert rewritten.follow(TEXT, edited, mark) == mark  # the edited line keeps its mark
    gone = TEXT.replace("GROOM: I bought 40 shares of one coin.\n", "")
    assert rewritten.follow(TEXT, gone, mark) == []


def test_the_version_shows_its_marks_until_approved(owner, db):
    made = _make(owner, text=TEXT)
    url = f"/scripts/{made['id']}"
    draft = db.query(ScriptDraft).filter_by(script_id=made["id"], slot=0).one()
    draft.rewritten = [{"line_index": 2, "was": "I bought 40 hoodies to resell."}]
    db.commit()
    shown = owner.get(url).json()["versions"][0]["rewritten"]
    assert shown == [{"line_index": 2, "was": "I bought 40 hoodies to resell.",
                      "text": "GROOM: I bought 40 shares of one coin."}]  # fmt: skip
    owner.put(f"{url}/drafts/0", json={"text": TEXT.replace("one coin", "a meme coin")})
    kept = owner.get(url).json()["versions"][0]["rewritten"]
    assert kept[0]["text"] == "GROOM: I bought 40 shares of a meme coin."  # still marked
    owner.post(f"{url}/drafts/0/approve")
    assert owner.get(url).json()["versions"][0]["rewritten"] == []
