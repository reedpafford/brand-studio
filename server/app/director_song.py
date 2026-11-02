"""The director's song and narration (Freestyle Song and Narrated, the Producer; the Director's
prompt side): in a song or narrated video the audio is the clock, so it comes right after the
treatment and before the plan. `song` makes the version's song takes (the version's style
line; a remake's note is added to that one request, never to the frozen version) and uses one
once they're timed; `narration` makes the narrator's read and uses it. Each is remade once a
run at most. The director judges a timed take without listening: when its first line is
sung (`hook_at`) and which lines weren't heard as written (`missing`)."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app import music, narration, song_takes
from app.models.accounts import User
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.songs import SongTake

REMAKES = 2  # a run's song (or narration) made again, with a note (Song-Producer: 2)
HEARD = 0.6  # a line counts as heard as written from this share of its words (take words)
HOOK = 0.5  # the first line sung: half its words heard
NO_SONG = "Refused: this video has no song."
NO_NARRATOR = "Refused: this video has no narrator."
AGAIN = f"Refused: the {{what}} was made again {REMAKES} times this run."
OFF = "Refused: songs aren't switched on here yet."
REFUSED = (music.REFUSED, music.REFUSED_IN_VIDEO)  # the words or style refused: never as is


def kind(db: Session, project: Project) -> str | None:
    """ "song" or "narrated" for a video timed to its audio; else None."""
    found = narration.video_kind(db, project)
    return found if found in narration.TIMED else None


def _take(db: Session, take: SongTake, used: int | None) -> dict:
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
            "missing": [x["text"] for x in lines if (x.get("heard") or 0) < HEARD]
            if take.timing is not None else None}  # fmt: skip


def state(db: Session, project: Project) -> dict | None:
    """What the director reads: {state none | making | ready | failed, takes, used_take_id}."""
    if kind(db, project) is None:
        return None
    takes = [_take(db, t, project.song_take_id) for t in song_takes.for_video(db, project)]
    states = {t["state"] for t in takes}
    now = ("none" if not takes else "making" if states & {"making", "timing"}
           else "ready" if "ready" in states else "failed")  # fmt: skip
    return {"state": now, "takes": takes, "used_take_id": project.song_take_id}


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
    a run (counted in `run`)."""
    tool, note = decision["tool"], (decision.get("note") or "").strip()
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
    if ready and not note:
        if project.song_take_id in {t.id for t in ready}:
            return f"The {what} is set: take {_number(db, project.song_take_id)}."
        best = next((t for t in ready if t.preferred), None) or min(
            ready, key=lambda t: (len(_take(db, t, None)["missing"] or []), t.id))  # fmt: skip
        song_takes.use_in_video(db, project, best)
        return f"Using take {best.number} for the {what}."
    if takes and not note:
        failed = [t for t in takes if song_takes.state(db, t)[0] == "failed"]
        if len(failed) != len(takes):
            return f"Refused: the {what} is still being made."
        reason = song_takes.state(db, failed[0])[1] or ""
        if reason in REFUSED or run.get("song_retries", 0) >= 1:  # the same would fail again
            return f"Refused: the {what} didn't come out ({reason}) Make it again with a note."
        song_takes.try_again(db, user, failed[0], kie=_real(db, found))  # free unless made
        run["song_retries"] = run.get("song_retries", 0) + 1
        return f"Trying the {what} again: the service failed, nothing was charged."
    if takes and run.get("songs", 0) >= REMAKES:
        return AGAIN.format(what=what)
    if not _on(db, draft):
        return OFF
    song_takes.make(db, user, draft, project, kie=_real(db, found), note=note)
    if takes:  # a remake; the first song's note is its style line, not a remake
        run["songs"] = run.get("songs", 0) + 1
    return f"Making the {what}{f' ({note})' if note else ''}."


def _real(db: Session, found: str) -> float:
    """A real song through KIE's price (song_takes.real_songs); a narration is never one."""
    return 0.0 if found == "narrated" else song_takes.real_songs(db, _settings())


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
