"""A script pasted as a screenplay (video 233: "MAYA" alone on a line, her words under it) is
read as the house's "MAYA: …" script: the same roles, speakers and spoken words."""

from app import prompts
from app import script_library as lib
from app.models.freestyles import Freestyle
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.prompts import check
from app.script_cast_read import _speakers
from tests.conftest import first_brand
from tests.test_script_library import _make

SCREENPLAY = """INT. KITCHEN - NIGHT

Maya stares at her phone.

MAYA
(quietly)
I never wanted this.
Not like this.

TOM (O.S.)
Then why are you here?

MAYA (CONT'D)
Because you asked.

CUT TO:"""
HOUSE = """INT. KITCHEN - NIGHT

Maya stares at her phone.

MAYA: I never wanted this. Not like this.
(quietly)

TOM (O.S.): Then why are you here?

MAYA: Because you asked.

CUT TO:"""


def test_a_screenplay_is_read_as_the_house_script_with_the_same_cast_and_words(owner, db):
    assert check.screenplay(SCREENPLAY) == HOUSE
    pasted, house = _make(owner, text=SCREENPLAY), _make(owner, text=HOUSE)
    assert pasted["versions"][0]["words"] == house["versions"][0]["words"]
    texts = [
        owner.get(f"/scripts/{s['id']}").json()["versions"][0]["text"] for s in (pasted, house)
    ]
    assert texts == [HOUSE, HOUSE]
    assert prompts.number_lines(texts[0]) == prompts.number_lines(HOUSE)  # the numbered lines
    for made in (pasted, house):
        assert _speakers(db, db.get(Script, made["id"])) == {"Maya": [0], "Tom": [0]}
    edited = _make(owner, text="")  # written into the script's own box
    r = owner.put(f"/scripts/{edited['id']}/drafts/0", json={"text": SCREENPLAY})
    assert r.json()["versions"][0]["text"] == HOUSE
    for kind in ("song", "narrated"):  # a song's CHORUS is no one; a narration has one voice
        assert lib.house(Script(kind=kind), SCREENPLAY) == SCREENPLAY
    body = {"type": "dialogue", "look": "house", "shape": "9:16", "text": SCREENPLAY,
            "brand_id": first_brand(owner)}  # fmt: skip
    sent = owner.post("/freestyles", json=body)  # New video, as video 233 was pasted
    assert sent.status_code == 201, sent.text
    video = db.get(Project, db.get(Freestyle, sent.json()["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    assert db.get(ScriptDraft, video.script_draft_id).text == HOUSE


def test_headings_transitions_and_directions_are_never_speakers():
    action = "INT. KITCHEN - NIGHT\nShe waits.\n\nCLOSE ON THE PHONE\nIt buzzes.\n\nFADE OUT."
    assert check.screenplay(action) == action
    for line in ("EXT. STREET - DAY", "CUT TO:", "FADE IN:", "SMASH CUT TO BLACK.", "LATER",
                 "MONTAGE", "SUPER: fomo", "I never wanted this."):  # fmt: skip
        assert check._cue(line) is None, line
    assert check._cue("DR. PICKLE (V.O.)") == "DR. PICKLE (V.O.)"
    house = "MAYA: Hi.\nBOOM\nThe door blows."  # labelled already: as it is
    assert check.screenplay(house) == house
    said = "SUPER: fomo\n\nMAYA\nHi.\n\nMAYA\nBye."  # a direction's colon is no speaker's label
    assert check.screenplay(said) == "SUPER: fomo\n\nMAYA: Hi.\n\nMAYA: Bye."


# QA on #1401: one line in capitals in an ordinary script is never a speaker
ORDINARY = [
    "Nate opens the app.\nFOMO\nThe chart climbs.",
    "WHERE DID THE FOOD GO",
    "NO WAY",
    "THE DIP\nYour gut is a mess.",
    "NBA\nThe game is on.",
    "OPEN",
    "DOWNLOAD FOMO\nLink in bio.",
    "She waits.\n\nNO WAY\nShe laughs.\n\nOPEN\nThe door swings.\n\nNBA\nThe game is on.",
    "He reads it.\n\nFOMO\nThe app opens.\n\nFOMO\nThe chart climbs.",  # the brand, twice
]


def test_an_ordinary_script_with_a_line_in_capitals_is_left_as_it_is(owner):
    for text in ORDINARY:
        assert check.screenplay(text, "fomo") == text, text
    made = _make(owner, text="")  # the editor's autosave never rewrites under the cursor
    for text in ORDINARY:
        r = owner.put(f"/scripts/{made['id']}/drafts/0", json={"text": text})
        assert r.json()["versions"][0]["text"] == text, text
    two = "INT. CAR - DAY\nMAYA\nHi.\nTOM\nHey.\nMAYA\nBye."  # one name twice: a screenplay
    assert check.screenplay(two) == "INT. CAR - DAY\nMAYA: Hi.\nTOM: Hey.\nMAYA: Bye."
