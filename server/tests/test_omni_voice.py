"""One voice across Omni pieces (Reed, 9 Nov: "if you prompt the voice the same for each clip, it
should not vary that much"): Omni takes no voice input, so each speaker's voice is set once for
the video and every Omni clip they speak in carries it word for word. Free: no paid calls."""

import copy

from app import director, model_map
from app.clip_prompts import with_cast
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.voices import Voice
from app.prompts.schemas import Breakdown, ClipPrompt
from app.voices import voice_of
from tests.test_breakdown import BREAKDOWN, _shot
from tests.test_cast_roles import _video

WARM, COCKY = "a woman in her 40s, low and warm, unhurried", "a teen boy, quick and cocky"
SHOTS = "Shots (hard cuts):\nShot 1 | 0-3 s. {}\nKeep: Everyone as in their pictures.\nAudio: x."


def _treat(db, project: Project, voices: list[dict], **more) -> None:
    db.add(Job(workspace_id=project.workspace_id, kind="write-claude", provider="claude",
               project_id=project.id, input={"step": "treatment", **more},
               output={"voices": voices}, status=JobStatus.succeeded))  # fmt: skip
    db.commit()


def _saved(db, project: Project, said: str) -> int:
    voice = Voice(workspace_id=project.workspace_id, brand_id=project.brand_id, kind="described",
                  name="Mia's voice", provider="minimax", description=said)  # fmt: skip
    db.add(voice)
    db.flush()
    return voice.id


def _omni(owner, editor, db) -> tuple[Project, int, Breakdown]:
    """Mom (Mia) speaks in clips c1 and c2, Nate (Kid) only in c1; the video is on Omni 1.2,
    and two treatments were written, the second wording Mom's voice another way."""
    pid, mia, _ = _video(owner, editor, db)
    project = db.get(Project, pid)
    project.video_model = model_map.OMNI
    _treat(db, project, [{"who": "Mom", "sounds": WARM}, {"who": "Nate", "sounds": COCKY}])
    _treat(db, project, [{"who": "Mom", "sounds": "a shrill young woman"}])
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"].append(_shot("1.3", [5], "Mom (O.S.)", "Fine.", 1))
    bd["clips"] = [{"id": "c1", "shot_ids": ["1.1", "1.2"], "seconds": 4, "seam": "-"},
                   {"id": "c2", "shot_ids": ["1.3"], "seconds": 3, "seam": "-"}]  # fmt: skip
    return project, mia, Breakdown.model_validate(bd)


def _written(db, project, bd, clip_id: str, prompt: str = "") -> list[str]:
    said = prompt or "Audio: x.\n" + SHOTS.format('Mom (in English, sharp): "Fine."')
    clip = ClipPrompt(clip_id=clip_id, seconds=3, references=[], prompt=said)
    return with_cast(db, project, clip, bd).prompt.splitlines()


def test_every_omni_clip_says_each_speakers_voice_in_the_words_first_set(owner, editor, db):
    project, _, bd = _omni(owner, editor, db)
    mom, nate = f"Mom's voice: {WARM}.", f"Nate's voice: {COCKY}."
    c1, c2 = _written(db, project, bd, "c1"), _written(db, project, bd, "c2")
    assert c1[1:4] == [mom, nate, "Shots (hard cuts):"]  # before the shots, in speaking order
    assert c2[1:3] == [mom, "Shots (hard cuts):"]  # the same words; Nate doesn't speak here
    again = _written(db, project, bd, "c1", "\n".join(c1))
    assert again == c1  # doing it again changes nothing
    older = _written(db, project, bd, "c2", "\n".join(c2).replace(WARM, "breathy"))
    assert older == c2  # an older wording of hers is replaced, never said twice
    project.video_model = "seedance-2.5"
    assert not any("'s voice: " in x for x in _written(db, project, bd, "c1"))  # only on Omni


def test_a_voice_saved_on_the_character_wins_over_the_treatments(owner, editor, db):
    """In its own words, spaces tidied and cut between words at about 200 characters."""
    project, mia, bd = _omni(owner, editor, db)
    db.get(LibraryItem, mia).voice_id = _saved(db, project, "late 40s,  tired, warm")
    db.commit()
    c1 = _written(db, project, bd, "c1")
    assert c1[1:3] == ["Mom's voice: late 40s, tired, warm.", f"Nate's voice: {COCKY}."]
    db.get(Voice, db.get(LibraryItem, mia).voice_id).description = "husky, " * 70  # 490 chars
    db.commit()
    line = _written(db, project, bd, "c1")[1]
    assert line.startswith("Mom's voice: husky, husky") and len(line) <= 220
    assert line.endswith("husky.")  # never half a word


def test_a_speaker_gets_the_voice_named_exactly_theirs_before_a_looser_match():
    """QA on #1487: the loose label match gave Woman 2 Woman 1's voice and Ex-Bride Bride's."""
    pairs = [("Woman 1", "Woman 2"), ("Bride", "Ex-Bride"), ("Guy 1", "Guy 2"),
             ("Old Man", "Young Man")]  # fmt: skip
    for a, b in pairs:
        for sounds in ([([a], "A"), ([b], "B")], [([b], "B"), ([a], "A")]):  # either order
            assert (voice_of(a, sounds), voice_of(b, sounds)) == ("A", "B"), (a, b)
    assert voice_of("GROOM", [(["Kid", "Nate, the teen groom"], "C")]) == "C"  # loose, if none
    assert voice_of("Dad", [(["Mom"], "A")]) == ""


def test_the_treatment_later_steps_read_shows_the_voices_the_clips_say(owner, editor, db):
    """QA on #1487: a later treatment's rewording (or a saved voice) never reaches the plan,
    the clip prompts or the director: they read the words set. A treatment its own check
    replaced sets nothing."""
    project, mia, _ = _omni(owner, editor, db)
    _treat(db, project, [{"who": "Dad", "sounds": "gravelly"}], redone=True)
    told = director.treatment(db, project)["voices"]
    assert told == [{"who": "Mom", "sounds": WARM}, {"who": "Nate", "sounds": COCKY}]
    db.get(LibraryItem, mia).voice_id = _saved(db, project, "late 40s, tired, warm")
    db.commit()
    block = director.treatment_block(db, project)
    assert '"sounds": "late 40s, tired, warm"' in block and "shrill" not in block
