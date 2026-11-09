"""A note in brackets in a script is direction, never spoken: a line that is only a note
("[she looks at the camera and sighs]", "[cut to the app]") and a note inside a spoken line
("I said [quietly] no"). "[Tag] text" lines work as before. The breakdown still sees them."""

import copy
import json
from types import SimpleNamespace

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app import (
    audition,
    breakdown_fix,
    director_song,
    line_change,
    locked_line,
    narration,
    take_words,
    watch_cut,
)
from app.models.songs import SongTake
from app.prompts import check, number_lines, spoken_words
from app.prompts.schemas import (
    Breakdown,
    ClipPrompt,
    ClipPrompts,
    PlanLine,
    PlanScene,
    ScenePlan,
)
from tests.test_breakdown import BREAKDOWN
from tests.test_migrations import _row

PROSE = (
    "My gut was a mess.\n[she looks at the camera and sighs]\n  [cut to the app]  \n"
    "I said [quietly] no.\n[Camera] Slow push in.\nThen came the greens."
)
SAID = "My gut was a mess.\nI said no.\nThen came the greens."


def test_the_narrator_never_reads_a_note(monkeypatch):
    assert check.narration_text(PROSE) == SAID
    assert narration.job(PROSE)["input"]["prompt"] == SAID  # the talker's take says the same
    monkeypatch.setattr("app.song_takes.words", lambda db, draft, project: PROSE)
    monkeypatch.setattr("app.talker.minimax", lambda db, project: False)
    drafts = SimpleNamespace(get=lambda model, n: object())  # the voice audition reads it too
    assert audition.line(drafts, SimpleNamespace(script_draft_id=1)) == " ".join(SAID.split("\n"))
    vo = "SCENE 1\nBISCUIT (V.O.): Day one.\n[cut to the bowl]\nBISCUIT (V.O.): Nope [beat] gone."
    assert check.narration_text(vo) == "Day one.\nNope gone."


def test_a_note_never_counts_as_spoken_words_or_time():
    assert spoken_words(PROSE) == len(SAID.split())
    assert spoken_words("MAYA: I said [quietly] no.\n[she sighs]") == 3
    assert check._said("[cut to the app]", False) == "" == check._said("[Camera] Push.", False)
    assert check._said("MAYA: I said [quietly] no.", True) == "I said no."
    assert check.narrator("SCENE 1\n[she sighs]") is None  # a silent story: no narrator


def test_the_word_checks_never_want_a_note_heard():
    heard = [{"word": w, "start": n * 0.4, "end": n * 0.4 + 0.3}
             for n, w in enumerate(SAID.split())]  # fmt: skip
    take = SongTake(kind=narration.KIND, lyrics=PROSE, timing={"words": heard})
    lines = [{"text": x, "heard": 1.0} for x in check.narration_text(PROSE).splitlines()]
    assert director_song._missing(take, lines) == []
    assert narration.extras(check.narration_text(PROSE), heard) == []
    assert not {"sighs", "cut", "quietly"} & watch_cut._script_words(PROSE)


def test_a_shot_line_drops_its_note_and_still_matches_the_script():
    """The breakdown reads the script with its notes (direction); a shot's line, what the
    video model says, never keeps one, and still matches the script's words."""
    script = "SCENE 1\nMOM: Nate, where is all your money?\nNATE: I bought [quietly] the dip."
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["script_lines"] = [1, 2]
    bd["scenes"][0]["shots"][1].update(script_lines=[3], line="I bought [quietly] the dip.")
    plan = Breakdown.model_validate(bd)
    assert plan.scenes[0].shots[1].line == "I bought the dip."
    assert "line differs" not in " ".join(check.breakdown(script, plan, {}, 4, 15))
    assert breakdown_fix._said("NATE: I bought [quietly] the dip.") == "I bought the dip."
    assert "3| NATE: I bought [quietly] the dip." in number_lines(script)  # what the steps read
    assert check.redo_note('Say "I bought [quietly] the dip." slower.', plan, "c1") == []
    assert check.redo_note('Say "I bought the chips." instead.', plan, "c1")  # still refused
    edited = line_change._with_line(bd, {"line": 3, "old": "the dip", "new": "the chips [beat]"})
    stored = edited["scenes"][0]["shots"][1]["line"]  # the owner's line change, as saved
    assert (
        stored == "I bought the chips." == Breakdown.model_validate(edited).scenes[0].shots[1].line
    )


def test_a_note_under_a_screenplay_speaker_stays_direction():
    pasted = "INT. KITCHEN\n\nMAYA\n[she sighs]\nI never wanted this.\n\nTOM (O.S.)\nThen why?"
    assert check.screenplay(pasted) == (
        "INT. KITCHEN\n\nMAYA: I never wanted this.\n[she sighs]\n\nTOM (O.S.): Then why?"
    )


def test_a_minimax_reading_copied_with_a_note_is_read_without_it():
    voice = narration.MINIMAX_VOICES[0]
    sent = narration.job("I said [quietly] no.", voice, reading="I said [quietly] <#0.2#> no.")
    assert sent["input"]["text"] == "I said <#0.2#> no."


def test_a_song_line_marked_lip_sync_keeps_its_words_in_a_scenes_length():
    """QA on #1490: "[Lip sync] words" is a song's mark, not a [tag] line: its words count."""
    lyrics = "[Chorus]\n[Lip sync] " + "la " * 30
    lines = [PlanLine.model_construct(line=2, product=None)]
    scene = PlanScene.model_construct(id=1, place="EXT. PARK", cast=[], lines=lines)
    found = check.plan(lyrics, ScenePlan.model_construct(scenes=[scene]), [], [], "song", 4)
    assert any("scene 1 runs about" in p for p in found)


def _saved(tmp_path, plans: dict):
    """A database at n44 with these plans saved (the first also as a version's), then n45."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path}/m.db")
    command.upgrade(cfg, "n44")
    engine = create_engine(cfg.get_main_option("sqlalchemy.url"))
    with engine.begin() as conn:
        for n, data in plans.items():
            _row(conn, "breakdowns", id=n, project_id=1, data=data)
        _row(conn, "script_drafts", id=1, breakdown=plans[1])
        _row(conn, "script_drafts", id=2, slot=1, breakdown=None)
    command.upgrade(cfg, "n45")
    return cfg, engine


def _plans(engine) -> list:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT data FROM breakdowns ORDER BY id")).scalars().all()
        drafts = conn.execute(text("SELECT breakdown FROM script_drafts ORDER BY id")).scalars()
        return [json.loads(x) if x else x for x in [*rows, *drafts.all()]]


def test_n45_takes_notes_out_of_saved_shot_lines_once(tmp_path):
    """Plans saved before #1490 kept a note in a shot's line: n45 takes it out, in a song plan
    and a version's saved plan too; a row that isn't a plan is left alone; again, no change."""
    plan = {"scenes": [{"shots": [{"id": "1.1", "line": "I bought [quietly] the dip."},
                                  {"id": "1.2", "line": None}]}]}  # fmt: skip
    sung = {"id": "1.1", "line": "Bark [Lip-sync]", "sung": True}
    song = {"scenes": [{"shots": [sung]}], "song": {"take_id": 3}}
    odd = [{"scenes": "x"}, {"scenes": [{"shots": [1, {"line": 5}]}]}, [], {}]
    cfg, engine = _saved(tmp_path, {1: plan, 2: song, **dict(enumerate(odd, 3))})
    plans = _plans(engine)
    assert [s["line"] for s in plans[0]["scenes"][0]["shots"]] == ["I bought the dip.", None]
    assert plans[1] == {**song, "scenes": [{"shots": [{**sung, "line": "Bark"}]}]}
    assert plans[2:6] == odd
    assert plans[6] == plans[0] and plans[7] is None
    command.downgrade(cfg, "n44")
    command.upgrade(cfg, "n45")
    assert _plans(engine) == plans


def test_an_old_plan_with_a_note_gets_prompts_its_checks_accept(tmp_path):
    """QA on #1490: the clip-prompt writer is sent the saved plan as stored. After n45 it
    quotes the line the check wants, the take word check hears it, a locked line finds it."""
    old = copy.deepcopy(BREAKDOWN)
    old["scenes"][0]["shots"][1]["line"] = "I bought [quietly] the dip."
    stored = _plans(_saved(tmp_path, {1: old})[1])[0]
    shots = stored["scenes"][0]["shots"]
    written = "\n".join(f'Shot {s["id"]} | {s["speaker"]}: "{s["line"]}"' for s in shots)
    cp = ClipPrompts(clips=[ClipPrompt(clip_id="c1", seconds=5, references=[], prompt=written)])
    found = check.clip_prompts(Breakdown.model_validate(stored), cp, 30, 10)
    assert not [p for p in found if "word for word" in p], found  # the shape's checks aside
    heard = [{"text": "Nate, where is all your money?", "start": 0.0, "end": 2.4},
             {"text": "I bought the dip.", "start": 2.5, "end": 4.0}]  # fmt: skip
    lines = [{"who": s["speaker"], "text": s["line"]} for s in shots]
    assert take_words.compare(lines, heard, "", "", []) == []
    assert locked_line._in("bought the dip", shots[1]["line"])
