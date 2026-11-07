"""The director's song and narration (Freestyle Song and Narrated, the Producer; the Director's
prompt side): in a song or narrated video the audio is the clock, so it comes right after the
treatment and before the plan. `song` makes the version's song takes (the version's style
line; a remake's note is added to that one request, never to the frozen version) and uses one
once they're timed; `narration` makes the narrator's read and uses it. Each is remade once a
run at most. The director judges a timed take without listening: when its first line is
sung (`hook_at`), which lines weren't heard as written (`missing`) and, in a narration, where
the brand's name was heard wrong (`misheard`), so it's read again with a note before the plan."""

import re
from decimal import Decimal

from sqlalchemy.orm import Session

from app import music, narration, song_takes, song_timing, take_words, voices
from app.models.accounts import User
from app.models.brands import Brand
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.songs import SongTake

REMADE = "audio_remakes"  # the run's count of them, a song's or a narration's alike
REMAKES = 2  # a run's song (or narration) made again, with a note (Song-Producer: 2)
HEARD = 0.6  # a line counts as heard as written from this share of its words (take words)
HOOK = 0.5  # the first line sung: half its words heard
CLOSE = 0.8  # a name of more than one word: this close in letters is the name said wrong
NO_SONG = "Refused: this video has no song."
NO_NARRATOR = "Refused: this video has no narrator."
AGAIN = f"Refused: the {{what}} was made again {REMAKES} times this run."
OFF = "Refused: songs aren't switched on here yet."
NO_STYLE = "Refused: the first song needs its style line as the note (genre, vocal, tempo)."
REFUSED = (music.REFUSED, music.REFUSED_IN_VIDEO)  # the words or style refused: never as is


def kind(db: Session, project: Project) -> str | None:
    """ "song" or "narrated" for a video timed to its audio; else None."""
    found = narration.video_kind(db, project)
    return found if found in narration.TIMED else None


def _bare(word: str) -> str:
    """A word as compared: "Fomo’s" reads "fomo" (the possessive dropped)."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"'s$", "", word.lower().replace("’", "'").strip(
        ".,!?;:…\"“”")))  # fmt: skip


def _near(heard: list[str], name: list[str]) -> bool:
    """A run of heard words that is the brand's name said wrong: each word one letter off at
    most, or, for a name of more than one word, its letters close ("Iron Pause")."""
    if heard == name:
        return False
    if all(h == n or take_words._off_by_one(h, n) for h, n in zip(heard, name, strict=True)):
        return True
    joined, want = "".join(heard), "".join(name)
    return len(name) > 1 and joined[:1] == want[:1] and take_words._close(joined, want) >= CLOSE


def misheard(timing: dict | None, brand: str, script: str = "") -> list[dict] | None:
    """The brand's name heard wrong in a timed narration ("Fobo" for fomo, "Iron Pause" for
    Iron Paws), from its words on the trimmed track; None until it's timed. Words the script
    itself has, as written ("user"), are never flagged."""
    if timing is None:
        return None
    words = timing.get("words") or []
    name = [b for w in brand.split() if (b := _bare(w))]
    written = f" {' '.join(_bare(w) for w in script.split())} "
    found, i = [], 0
    while name and i + len(name) <= len(words):
        run = words[i : i + len(name)]
        bare = [_bare(w["word"]) for w in run]
        if _near(bare, name) and f" {' '.join(bare)} " not in written:
            found.append({"word": brand, "heard": " ".join(w["word"] for w in run),
                          "at": run[0]["start"]})  # fmt: skip
            i += len(name)
        else:
            i += 1
    return found


def _missing(take: SongTake, lines: list[dict]) -> list[str]:
    """Lines not heard as written. A song's: under HEARD of its words. A narration's: any word
    lost, by its letters against everything heard, as the trim check compares (one dropped
    "probiotics" is a miss)."""
    if take.kind != narration.KIND:
        return [x["text"] for x in lines if (x.get("heard") or 0) < HEARD]
    heard = narration.letters((take.timing or {}).get("words") or [])
    return [x["text"] for x in lines if narration.letters([{"word": x["text"]}]) not in heard]


def _take(db: Session, take: SongTake, used: int | None, brand: str = "") -> dict:
    status = song_takes.state(db, take)[0]
    timing = take.timing or {}
    lines = timing.get("lines") or []
    sung = [x for x in lines if (x.get("heard") or 0) >= HOOK]
    gaps = [b["start"] - a["end"] for a, b in zip(sung, sung[1:], strict=False)]
    return {"id": take.id, "number": take.number, "state": status, "used": take.id == used,
            "preferred": bool(take.preferred), "timed": take.timing is not None,
            "seconds": timing.get("seconds"),
            "sections": [s.get("name") for s in timing.get("sections") or []],
            "hook_at": sung[0]["start"] if sung else None,
            "longest_gap": round(max(gaps), 2) if gaps else None,  # an instrumental break
            "tail": round(timing["seconds"] - sung[-1]["end"], 2) if sung else None,  # outro
            "missing": _missing(take, lines) if take.timing is not None else None,
            "pace": timing.get("pace"),  # words a second while speaking, as measured
            **({"misheard": misheard(take.timing, brand, take.lyrics)}
               if take.kind == narration.KIND else {}),
            **({"extras": _extras(take)} if take.kind == "song" else {})}  # fmt: skip


def _extras(take: SongTake) -> list[dict] | None:
    """Sung but not in the lyrics (ad-libs, an extra chorus); None until timed. Timings read
    before extras were saved work them out from their words."""
    if take.timing is None:
        return None
    if "extras" in take.timing:
        return take.timing["extras"]
    return song_timing.extras(take.lyrics, take.timing.get("words") or [])


def state(db: Session, project: Project) -> dict | None:
    """What the director reads: {state none | making | ready | failed, takes, used_take_id};
    a song's also has the `style` it's sung in and the brand's `recent_styles`, a
    narration's the `say` note it's read again with when the brand's name is heard wrong."""
    found = kind(db, project)
    if found is None:
        return None
    brand = db.get(Brand, project.brand_id)
    made = song_takes.for_video(db, project)
    takes = [_take(db, t, project.song_take_id, brand.name) for t in made]
    states = {t["state"] for t in takes}
    now = ("none" if not takes else "making" if states & {"making", "timing"}
           else "ready" if "ready" in states else "failed")  # fmt: skip
    out = {"state": now, "takes": takes, "used_take_id": project.song_take_id}
    if found == "narrated":  # the note a narration with the name wrong is read with
        out["say"] = say(brand)
        used = next((t.voice for t in made if t.id == project.song_take_id), None)
        said = used or _voice(db, project)
        if own := voices.for_director(db, project.workspace_id, project.brand_id, said):
            out["voice"] = own  # a cloned voice's state and when it may expire
        if note := voices.host_note(db, project):
            out["voice_note"] = note  # the host's own voice was removed: say what to do
        out["pace_wanted"] = target(db, project)  # the style's words a second
    if found == "song":
        used = [t for t in made if t.id == project.song_take_id]
        take = (used or sorted(made, key=lambda t: t.id))[-1] if made else None
        draft = db.get(ScriptDraft, project.script_draft_id)
        out["style"] = (music.sung_style(db.get(Job, take.job_id).input) if take
                        else draft.style_line.strip())  # fmt: skip
        out["recent_styles"] = music.recent_styles(db, project.brand_id)
    return out


def say(brand: Brand) -> str:
    """The pronunciation note for the narrator ("Say fomo as FOH-moh.")."""
    said_as = take_words.say(brand)
    if said_as == brand.name:
        return f"Say the name {brand.name} clearly, as it's written."
    return f"Say {brand.name} as {said_as}."


def _on(db: Session, draft: ScriptDraft) -> bool:
    """As the songs route's own switch (routes/songs.songs_on), from the server's settings."""
    settings = _settings()
    if song_takes.narrated(db, draft):
        return bool(settings.fake_providers or settings.generation_enabled)
    return bool(settings.fake_providers or settings.kie_suno)


def run(db: Session, user: User, project: Project, decision: dict, run: dict) -> str:
    """The tool: with `take_id`, use that timed take (free); with no note and a timed take,
    the best one; else make takes. The first song of a version with no style line takes its
    style from the note (the director's music words); after that a note is a remake, REMAKES
    a run (counted in `run`). A MiniMax narrator's `emotion` and `reading` ask like a note."""
    tool, note = decision["tool"], (decision.get("note") or "").strip()
    delivery = {k: decision[k] for k in ("emotion", "reading") if decision.get(k)}
    if delivery and (speed := _speed(db, project, delivery.get("emotion"))):
        delivery["speed"] = speed  # set from the last read's measured pace
    asked = note or delivery
    found = kind(db, project)
    if found is None or (tool == "song") != (found == "song"):
        return NO_SONG if tool == "song" else NO_NARRATOR
    draft = db.get(ScriptDraft, project.script_draft_id)
    what = "song" if found == "song" else "narration"
    takes = song_takes.for_video(db, project)
    ready = [t for t in takes if song_takes.state(db, t)[0] == "ready"]
    if (chosen := decision.get("take_id")) is not None:
        take = next((t for t in ready if t.id == chosen), None)
        if take is None:
            return f"Refused: take {chosen} isn't a finished {what} of this video."
        song_takes.use_in_video(db, project, take)
        return f"Using take {take.number} for the {what}."
    if ready and not asked:
        if project.song_take_id in {t.id for t in ready}:
            return f"The {what} is set: take {_number(db, project.song_take_id)}."
        best = next((t for t in ready if t.preferred), None) or min(
            ready, key=lambda t: _rank(_take(db, t, None), t.id))  # fmt: skip
        song_takes.use_in_video(db, project, best)
        return f"Using take {best.number} for the {what}."
    if takes and not asked:
        failed = [t for t in takes if song_takes.state(db, t)[0] == "failed"]
        if len(failed) != len(takes):
            return f"Refused: the {what} is still being made."
        reason = song_takes.state(db, failed[0])[1] or ""
        if reason in REFUSED or run.get("song_retries", 0) >= 1:  # the same would fail again
            return f"Refused: the {what} didn't come out ({reason}) Make it again with a note."
        last = run.get("song_note", "")  # the same request again: its style line too
        voice = run.get("song_voice") or narration.VOICE  # a narration keeps its voice
        song_takes.make(db, user, draft, project, kie=_real(db, found), note=last, voice=voice,
                        delivery=run.get("song_delivery"))  # fmt: skip
        run["song_retries"] = run.get("song_retries", 0) + 1  # charged only if it's made
        return f"Trying the {what} again: the service failed, nothing was charged."
    if takes and run.get(REMADE, 0) >= REMAKES:
        return AGAIN.format(what=what)
    if found == "song" and not note and not draft.style_line.strip():
        return NO_STYLE  # free: never a song with no genre, vocal or tempo (QA-10)
    if not _on(db, draft):
        return OFF
    kept = next((t.voice for t in takes if t.id == project.song_take_id), None)  # a remake's
    if kept and not voices.usable(db, project.workspace_id, project.brand_id, kept):
        kept = None  # its voice was removed since: the video's own voice now
    # a person's voice for the video: its settings, or their answer on a voice card (S4-01)
    picked = voices.picked(db, project) if found == "narrated" else None
    voice = (picked or decision.get("voice") or kept if found == "narrated" else None) or _voice(
        db, project
    )
    if not voices.usable(db, project.workspace_id, project.brand_id, voice):
        return f"Refused: the narrator's voice is one of {', '.join(narration.VOICES)}."
    song_takes.make(
        db, user, draft, project, kie=_real(db, found), note=note, voice=voice, delivery=delivery
    )  # a reading that changes a word is refused (422)
    run["song_note"], run["song_voice"], run["song_delivery"] = note, voice, delivery
    if takes:  # a remake; the first song's note is its style line, not a remake
        run[REMADE] = run.get(REMADE, 0) + 1
    return f"Making the {what}{f' ({note})' if note else ''}."


def target(db: Session, project: Project) -> tuple[float, float] | None:
    """The words a second the video's style (else its format) keeps, from its guide."""
    from app import guides
    from app.script_library import format_id

    script = narration.video_script(db, project)
    return guides.pace(project.look or "house", format_id(script)) if script else None


def _speed(db: Session, project: Project, emotion: str | None) -> float | None:
    """A MiniMax remake's speed: the last read in the same emotion, measured, brought to the
    style's pace (narration.retimed: "measure, don't guess"); None leaves the emotion's own."""
    want = target(db, project)
    done = [t for t in song_takes.for_video(db, project)
            if t.timing and t.timing.get("pace") and t.job_id]  # fmt: skip
    for take in sorted(done, key=lambda t: (t.id != project.song_take_id, -t.id)):
        made = narration.delivery(db.get(Job, take.job_id).input)
        if made and want and made["speed"] and (made["emotion"] or "auto") == (emotion or "auto"):
            return narration.retimed(made["speed"], take.timing["pace"], want) or made["speed"]
    return None


def _voice(db: Session, project: Project) -> str:
    """The narrator when none is picked: a person's for this video, else the video's own (its
    host's or its style's, e.g. Dr. Pickle's clone), else the MiniMax voice for a talker or a
    UGC presenter in one spot (talks or corner; Reed, 3 and 6 Nov: talker.minimax), else
    narration's."""
    from app import talker

    if own := voices.picked(db, project) or voices.default_for(db, project):
        return own
    return talker.VOICE if talker.minimax(db, project) else narration.VOICE


def _real(db: Session, found: str) -> float:
    """A real song through KIE's price (song_takes.real_songs); a narration is never one."""
    return 0.0 if found == "narrated" else song_takes.real_songs(db, _settings())


def _rank(take: dict, take_id: int) -> tuple:
    """The best take first: fewest lines missing, then the shorter (cheaper to film)."""
    return (len(take["missing"] or []), take["seconds"] or 0, take_id)


def _settings():
    from app.settings import get_settings

    return get_settings()


def _number(db: Session, take_id: int) -> int:
    return db.get(SongTake, take_id).number


def price(db: Session, draft: ScriptDraft) -> Decimal:
    """What a run's song or narration can cost at most: its first request and one remake."""
    from app.credits import estimate
    from app.models.script_library import Script

    script = db.get(Script, draft.script_id)
    if script.kind not in narration.TIMED or song_takes.preferred(db, draft):
        return Decimal(0)  # a version with a song already: its card has it (version_cost)
    ws = script.workspace_id
    if script.kind == "narrated":
        job = narration.job(draft.text)
        one = estimate(db, ws, "speech", song_takes._units(job), job)
    else:
        one = estimate(db, ws, "music", Decimal(1), {})
    return one * (1 + REMAKES)
