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
    lines = [
        {"who": "JAY", "text": t}
        for t in (
            "Into fomo. Yeah.",
            "Get Resilia today.",
            "It hit $4,200!",
            "Gonna be rich.",
            "Into it.",
        )
    ]
    for said in ("Into foe mo. Yeah.", "Get Re silly a today.", "It hit four thousand two hundred!",
                 "Going to be rich.", "Into it. Foe mo."):  # fmt: skip  # QA on #1428
        heard = [{"text": said, "start": 0, "end": 3, "words": _words(said, 0)}]
        run = take_words.compare(lines, heard, "fomo", "FOH-moh", [])
        assert not [f for f in run if f["kind"] == "extra"], (said, run)
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


def test_a_real_screen_is_the_clips_reference_never_a_cut_in(app, db, editor, approved):  # noqa: F811
    """Reed, 8 Nov (rule 13): the real product or screen is attached as the generation's
    reference, never pasted in as a flat full-frame still (run 287's pouch, mid-scene). The
    director has no cut-in tool; the switch only takes an older cut-in off."""
    from app import director_tools
    from app.director import video_state
    from app.models.accounts import User
    from app.models.projects import Project
    from app.routes.project_clips import AS_REFERENCE

    base, clip = approved
    project = db.get(Project, int(base.rsplit("/", 1)[1]))
    ed = db.query(User).filter_by(email="ed@example.com").one()
    (state,) = [c for c in video_state(db, project)["clips"] if c["clip_id"] == clip["clip_id"]]
    assert "inserts" not in state
    said = director_tools.run(db, ed, project, {"tool": "real_screen", "clip_id": clip["clip_id"],
                                                "shot_id": "1.2"}, app.state.storage)  # fmt: skip
    assert said == "Refused: there's no tool called real_screen."
    url = f"{base}/clips/{clip['id']}/inserts/1.2"
    on = editor.put(url, json={"use_real_image": True})
    assert (on.status_code, on.json()["detail"]) == (409, AS_REFERENCE)
    row = db.get(ProjectClip, clip["id"])
    row.real_images = {"1.2": True}  # an older video's cut-in stays until switched off
    db.commit()
    assert editor.put(url, json={"use_real_image": False}).status_code == 200
    db.expire_all()
    assert db.get(ProjectClip, clip["id"]).real_images == {"1.2": False}


@pytest.mark.parametrize(("name", "texts", "age"), [
    ("Jay", ["Jay is 19, plain and likeable, cap and hoodie."], "aged 19"),
    ("Jay", ["Jay is 19."], "aged 19"),
    ("Jay", ["JAY (19, plain and likeable)"], "aged 19"),
    ("Jay", ["JAY (19)"], "aged 19"),
    ("Jay", ["A 19-year-old Jay counts his cash."], "aged 19"),
    ("Jay", ["Jay, 19 years old, counts his cash."], "aged 19"),
    ("Jay", ["Jay, aged 19, counts his cash."], "aged 19"),
    ("Uncle Ray", ["Uncle Ray is in his 50s, broad, square-jawed."], "in his 50s"),
    ("Mia", ["MIA, mid-40s, a teacher"], "in their mid-40s"),
    ("Mia", ["MIA (mid-40s, a teacher)"], "in their mid-40s"),
    # QA on #1428: never an age from a time, a count, a score, money or a decade's noun
    ("Marcus", ["Marcus, 3 AM, trades in the dark."], ""),
    ("Marcus", ["MARCUS (3 AM)"], ""),
    ("Jay", ["Jay (2 of 3)"], ""),
    ("Jay", ["Jay is 5 for 5 on his trades."], ""),
    ("Jay", ["Jay, 30 seconds later, grins."], ""),
    ("Jay", ["Jay, 5 years into the job, quits."], ""),
    ("Jay", ["Jay is 20 bucks short."], ""),
    ("Jay", ["Jay, 24/7 on the app."], ""),
    ("Jay", ["Jay is 24/7 on it."], ""),
    ("Jay", ["Jay, 90s kid, grins."], ""),
    ("Jay", ["Jay is in his 90s kid phase."], ""),
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
    assert look.notes == "Nate, aged 19, plain and likeable"  # the note's words (video 284)
    assert "The character: Nate, aged 19" in prompts.sheet_prompt("character", look.notes)
    assert "<character>Nate, aged 19, plain" in prompts.look_fit_input(look.notes)
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
    for step in ("watch_cut", "director"):  # QA on #1428: a beat a person asked for stays
        assert "never a beat a person's note asked for" in prompts.system(step), step


def test_a_line_comes_early_in_its_shot_unless_the_setup_is_the_point():
    plan, clip = prompts.system("breakdown"), prompts.system("clip_prompts")
    assert "**A line comes early in its shot.**" in plan
    assert "Only when the setup is itself the point" in plan
    assert "the line comes at or near its start" in clip and "unless the setup is itself" in clip
    director = prompts.system("director")
    assert "real_screen" not in director  # rule 13: a reference, never a cut-in
    assert "**Unscripted words** (`unscripted` on a take)" in director


def test_a_mute_never_covers_a_word_its_finding_doesnt_name():
    """QA on #1428: a words-check span that would also silence another heard word (a script
    word, the brand, a figure) is never offered to the director's mute."""
    from app.director import _over_others

    said = [
        {"word": "Get", "start": 0.0, "end": 0.3},
        {"word": "fomo.", "start": 0.3, "end": 0.7},
        {"word": "Come", "start": 0.9, "end": 1.1},
        {"word": "on.", "start": 1.1, "end": 1.3},
    ]
    come = "“Come on.” at 0:00.9 isn't in the script, said with the line “Get fomo.”."
    assert not _over_others(come, [0.9, 1.3], said)  # only its own words: muted
    assert _over_others(come, [0.3, 1.3], said)  # it would take "fomo" with it: never
    assert not _over_others(
        "“That's fine” at 0:04.5 isn't in the script.",
        [4.5, 5.0],
        [{"word": "That's", "start": 4.5, "end": 4.7}, {"word": "fine", "start": 4.7, "end": 5.0}],
    )
