"""Video 245 (House, Dialogue), the critic's well-supported items: a line early in its shot, a
planned silence judged against the take, the brand's real screen at the word, a role's stated
age on its sheet, and unscripted words said inside a line. Stand-ins only."""

import pytest

from app import cast_roles, prompts, take_words, watch_cut
from app.models.clips import ProjectClip
from tests.test_cut_in import approved  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture

LINES = [{"who": "UNCLE RAY", "text": "I'll give you one. Then you're mowing my lawn."},
         {"who": "JAY", "text": "Give me six months."}]  # fmt: skip


def _words(text: str, start: float, step: float = 0.3) -> list[dict]:
    at = [round(start + n * step, 2) for n in range(len(text.split()))]
    return [{"word": w, "start": a, "end": round(a + 0.25, 2)}
            for w, a in zip(text.split(), at, strict=True)]  # fmt: skip


def test_words_said_inside_a_line_that_the_script_lacks_are_a_finding_to_mute():
    """245: "Come on." came right after Ray's line and was heard as one line with it, so the
    words check called it said and never flagged it."""
    said = "I'll give you one. Then you're mowing my lawn. Come on."
    heard = [{"text": "Give me six months.", "start": 1.0, "end": 2.1,
              "words": _words("Give me six months.", 1.0)},
             {"text": said, "start": 11.4, "end": 14.7, "words": _words(said, 11.4)}]  # fmt: skip
    (found,) = take_words.compare(LINES, heard, "fomo", "FOH-moh", [])
    assert found["kind"] == "extra" and found["text"].startswith("“Come on.” at 0:14.1 isn't")
    assert found["span"] == [14.1, 14.65] and "Then you're mowing my lawn." in found["text"]
    both = "Give me six months. I'll give you one. Then you're mowing my lawn."  # run together
    run = take_words.compare(
        LINES,
        [{"text": both, "start": 0, "end": 4, "words": _words(both, 0)}],
        "fomo",
        "FOH-moh",
        [],
    )
    assert not [f for f in run if f["kind"] == "extra"]  # the other line's words: never extra
    for line in ("Give me six months, uh.", "Give me six mumps."):  # a hesitation, a mishearing
        heard = [{"text": line, "start": 0, "end": 2, "words": _words(line, 0)},
                 {"text": LINES[0]["text"], "start": 3, "end": 5}]  # fmt: skip
        assert take_words.compare(LINES, heard, "fomo", "FOH-moh", []) == [], line
    untimed = [{"text": "Give me six months. Come on, man.", "start": 1, "end": 3},
               {"text": LINES[0]["text"], "start": 3, "end": 5}]  # fmt: skip
    (found,) = take_words.compare(LINES, untimed, "fomo", "FOH-moh", [])
    assert "span" not in found and "muted" not in found["text"]  # no times: no mute offered


def test_the_director_sees_unscripted_words_on_a_take(app, db, owner, editor):
    from app.director import video_state
    from app.models.checks import ItemCheck
    from tests.test_v6_quality import _delivered

    project = _delivered(app, owner, editor, db)
    row = db.query(ProjectClip).filter_by(project_id=project.id).first()
    finding = {
        "kind": "extra",
        "at": 14.1,
        "text": "“Come on.” at 0:14.1 isn't in the script.",
        "change_note": "Say only the script's lines.",
        "span": [14.1, 14.65],
    }
    db.add(ItemCheck(project_id=project.id, target="words", target_id=row.picked_take_id,
                     status="done", findings=[finding]))  # fmt: skip
    db.commit()
    clip = next(c for c in video_state(db, project)["clips"] if c["clip_id"] == row.clip_id)
    take = next(t for t in clip["takes"] if t["id"] == row.picked_take_id)
    assert take["unscripted"] == [finding["text"]]


def test_the_director_shows_the_brands_real_screen_at_the_word(app, db, editor, approved):  # noqa: F811
    """Generated numbers and screen changes garbled in 233, 226 and 245 ($0.00, "$41,2000").
    The director switches an insert shot to the brand's real screen, its figure drawn on it,
    as the Clips switch does: free, and it can put the generated one back."""
    from app import director_tools
    from app.director import video_state
    from app.models.accounts import User
    from app.models.projects import Project

    base, clip = approved
    project = db.get(Project, int(base.rsplit("/", 1)[1]))
    ed = db.query(User).filter_by(email="ed@example.com").one()
    (state,) = [c for c in video_state(db, project)["clips"] if c["clip_id"] == clip["clip_id"]]
    assert state["inserts"] == [{"shot_id": "1.2", "screen": "Buy", "real": False}]

    def run(**decision) -> str:
        said = director_tools.run(db, ed, project, {"tool": "real_screen", **decision},
                                  app.state.storage)  # fmt: skip
        db.commit()
        return said

    said = run(clip_id=clip["clip_id"], shot_id="1.2")
    assert said.startswith("Shot 1.2 of clip 1 shows the brand's real screen in the cut")
    assert db.get(ProjectClip, clip["id"]).real_images == {"1.2": True}
    assert editor.get(f"{base}/clips").json()[0]["inserts"][0]["use_real_image"] is True
    assert run(clip_id=clip["clip_id"], shot_id="1.2", value="off").endswith(
        "generated screen again."
    )
    assert db.get(ProjectClip, clip["id"]).real_images == {"1.2": False}
    assert run(clip_id=clip["clip_id"], shot_id="1.1") == (
        "Refused: That shot isn't an insert in this clip.")  # fmt: skip
    assert run(clip_id="", shot_id="1.2") == "Refused: name one clip."


@pytest.mark.parametrize(("name", "texts", "age"), [
    ("Jay", ["Jay is 19, plain and likeable, cap and hoodie."], "aged 19"),
    ("Jay", ["JAY (19, plain and likeable)"], "aged 19"),
    ("Jay", ["A 19-year-old Jay counts his cash."], "aged 19"),
    ("Uncle Ray", ["Uncle Ray is in his 50s, broad, square-jawed."], "in his 50s"),
    ("Mia", ["MIA, mid-40s, a teacher"], "in their mid-40s"),
    ("Jay", ["Jay, 6 months later, pulls up.", "JAY: Give me six months."], ""),
    ("Jay", ["Jay is 5 feet tall."], ""),
])  # fmt: skip
def test_the_age_a_role_is_given_reads_as_its_sheets_words(name, texts, age):
    assert cast_roles.stated_age(name, texts) == age


def test_a_roles_look_is_drawn_and_checked_at_its_stated_age(app, db, owner, editor):
    """245: Jay's role said only "Jay"; the note said "Jay is 19", and his sheet read ~30. The
    look made for the role carries the age into its sheet prompt and its fit check."""
    from app.models.accounts import User
    from app.models.library import LibraryItem
    from app.models.projects import Project
    from app.routes.project_assets import _make_look
    from tests.test_director import _made

    pid = _made(app, owner, editor, db)
    project = db.get(Project, pid)
    project.director_chat = [{"text": "Nate is 19, plain and likeable.", "run": "r"}]
    db.commit()
    slot = next(s for s in cast_roles.video_slots(db, project) if s.role.startswith("Nate"))
    slot.description = ""
    _make_look(db, db.get(User, project.created_by_id), project, slot)
    look = (db.query(LibraryItem).filter_by(owner_project_id=pid)
            .order_by(LibraryItem.id.desc()).first())  # fmt: skip
    assert look.notes == "Nate, aged 19"
    assert "The character: Nate, aged 19" in prompts.sheet_prompt("character", look.notes)
    assert "<character>Nate, aged 19</character>" in prompts.look_fit_input(look.notes)
    fit = prompts.system("look_fit")
    assert "a 19-year-old drawn as someone about 30" in fit


def test_a_cut_watch_trim_is_a_free_cut_of_a_planned_silence_never_a_script_word():
    """245: a planned 1.2 s silent reaction the take didn't perform, then 1.8 s of stare, left
    3.6 s of dead air, and the director offered the owner a trim instead of making it."""
    cut = [{"clip_id": "c1", "start": 0.0, "end": 8.0, "take_id": 78},
           {"clip_id": "c2", "start": 8.0, "end": 17.0, "take_id": 77}]  # fmt: skip
    words = [{"word": "Give", "start": 9.86, "end": 10.1}, {"word": "me", "start": 10.1,
              "end": 10.3}, {"word": "six", "start": 10.3, "end": 10.6},
             {"word": "months.", "start": 10.6, "end": 10.96}]  # fmt: skip
    base = {
        "says": "c1: a held stare where he should swallow",
        "kind": "story",
        "evidence": "picture",
        "fix": "trim",
        "note": "The plan's swallow isn't performed.",
    }
    answer = {"findings": [{**base, "clip_id": "c1", "start": 6.7, "end": 8.0},
                           {**base, "clip_id": "c2", "start": 9.5, "end": 10.5},
                           {**base, "clip_id": "c1", "start": 7.5, "end": 8.5}]}  # fmt: skip
    kept = watch_cut.checked(answer, cut, words, "JAY: Give me six months.")
    assert [(f["clip_id"], f["start"], f["fix"]) for f in kept] == [("c1", 6.7, "trim")]
    director = prompts.system("director")
    assert "a `trim` you make yourself with `edit_cut` (free" in director
    assert "never left to the owner" in director
    assert "judged against the take, not the plan" in prompts.system("watch_cut")


def test_a_line_comes_early_in_its_shot_unless_the_setup_is_the_point():
    plan, clip = prompts.system("breakdown"), prompts.system("clip_prompts")
    assert "**A line comes early in its shot.**" in plan
    assert "Only when the setup is itself the point" in plan
    assert "the line comes at or near its start" in clip and "unless the setup is itself" in clip
    director = prompts.system("director")
    assert "- `real_screen` (free, `clip_id`, `shot_id`)" in director
    assert "**Unscripted words** (`unscripted` on a take)" in director
