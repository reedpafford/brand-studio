"""The owner changes a published line on a video already made (Reed, 7 Nov: rule 31's owner
exception). On S3-14's card, as one more choice for the owner only, "Change the line" makes a
new version of the script with that line changed (a version of the library script, so the
script and its other videos stay as they are), and remakes only the clips whose shots carry
that line: their prompts and takes, and in a narrated video the narration, read again with the
new words, the clips under the other lines kept on its new timing. Then the cut and its watch.
It runs as a director run the owner's press already approved (no start card), with a note
saying exactly what to make again. An editor's card stays as S3-14 draws it."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.asks import Ask
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.projects import Project
from app.models.script_library import ScriptDraft

DO = "change_line"
TITLE = "Change the line"
OWNER_ONLY = "Only the owner can change the script's words."
MOVED = "That line has changed since. Ask again in the chat."
NOTE = (  # never quoting the words or "change … line" (a take's note can't: check.redo_note)
    "The owner wrote line {n} of the script again, in a new version. {what}; keep every other "
    "clip and take, then make the cut and watch it."
)


def _replaced(line: str, old: str, new: str) -> str:
    """The line with its words changed, as the script writes them (the first time it says it)."""
    import re

    return re.sub(re.escape(old), new.replace("\\", r"\\"), line, count=1, flags=re.I)


def line_of(text: str, words: str) -> int | None:
    """The script line (1-based) that says these words, else None."""
    from app.locked_line import _in

    return next((n for n, line in enumerate(text.splitlines(), 1) if _in(words, line)), None)


def _narrated(db: Session, project: Project) -> bool:
    from app.narration import video_kind

    return video_kind(db, project) == "narrated"


def clips_of(db: Session, project: Project, n: int) -> list[str]:
    """The clips of the newest plan whose shots carry script line `n`, in plan order."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    if bd is None:
        return []
    shots = {s["id"] for sc in bd.data.get("scenes", []) for s in sc.get("shots", [])
             if n in (s.get("script_lines") or [])}  # fmt: skip
    return [c["id"] for c in bd.data.get("clips", []) if shots & set(c["shot_ids"])]


def choice(db: Session, user: User, project: Project, words: str, new: str | None) -> dict | None:
    """The owner's "Change the line" on S3-14's card, or None (an editor; no new words; no
    clip says that line)."""
    from app import plans

    version = plans.script(db, project)
    new = (new or "").strip().strip("“”\"'‘’ ")
    if not user.is_owner or not new or version is None:
        return None
    n = line_of(version.text, words)
    clips = clips_of(db, project, n) if n else []
    if not clips:
        return None
    named = ", ".join(c.removeprefix("c") for c in clips)
    what = f"clip{'s' if len(clips) > 1 else ''} {named}"
    what += " and the narration are" if _narrated(db, project) else (
        " are" if len(clips) > 1 else " is")  # fmt: skip
    return {"title": TITLE, "do": DO, "line": n, "new": new[:200], "clips": clips,
            "why": f"A new version of the script says “{new}” for “{words}”. Only {what} made "
                   "again, then the cut"}  # fmt: skip


def price(db: Session, project: Project, found: dict) -> Decimal | None:
    """As its press can charge (rule 36: "up to"): each clip's prompt written again and its
    take, and a narrated video's narration read once more."""
    from app import narration
    from app.clip_prompts import rewrite_price
    from app.clip_takes import take_credits
    from app.credits import estimate

    rows = [_row(db, project, c) for c in found.get("clips") or []]
    if not rows or any(r is None for r in rows):
        return None
    total = rewrite_price(db, project, found["clips"])
    total += sum((take_credits(db, project, r) for r in rows), Decimal(0))
    if _narrated(db, project):
        from app import plans, song_takes

        text = _new_text(plans.script(db, project).text, found)
        job = narration.job(text)
        total += estimate(db, project.workspace_id, "speech", song_takes._units(job), job)
    return total


def cannot(db: Session, project: Project, found: dict, words: str, user: User | None) -> str:
    from app import plans

    if user is not None and not user.is_owner:
        return OWNER_ONLY
    version = plans.script(db, project)
    lines = version.text.splitlines() if version else []
    n = found.get("line") or 0
    if not (0 < n <= len(lines)) or line_of(version.text, words) != n:
        return MOVED
    if any(_row(db, project, c) is None for c in found.get("clips") or []):
        return MOVED
    return ""


def _row(db: Session, project: Project, clip_id: str) -> ProjectClip | None:
    return db.scalar(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                               ProjectClip.clip_id == clip_id))  # fmt: skip


def _new_text(text: str, found: dict) -> str:
    lines = text.splitlines()
    n = found["line"]
    lines[n - 1] = _replaced(lines[n - 1], found["old"], found["new"]) if found.get("old") else (
        lines[n - 1])  # fmt: skip
    return "\n".join(lines)


def press(db: Session, user: User, project: Project, ask: Ask, found: dict, storage) -> dict:
    """The owner's press: the new version, the plan on it with only the line's clips left to
    make again, the narration read again if it's narrated, and a run (already approved: the
    owner's press is the OK) whose note says what to make. Nothing else is made again."""
    from app import breakdown, cast_roles, clip_prompts, director, plans
    from app.credits import lock
    from app.db import utcnow
    from app.routes.scripts import save_version

    if not user.is_owner:
        raise HTTPException(403, OWNER_ONLY)
    found = {**found, "old": ask.subject}
    if why := cannot(db, project, found, ask.subject, user):
        raise HTTPException(409, why)
    lock(db, Project, project.id)
    version = plans.script(db, project)
    text = _new_text(version.text, found)
    old = db.get(ScriptDraft, project.script_draft_id)
    slot = db.scalar(select(func.max(ScriptDraft.slot)).where(
        ScriptDraft.script_id == old.script_id)) or 0  # fmt: skip
    keep = ("status", "style_line", "singer", "plan", "spoken_end_line", "approved_at",
            "approved_by_id", "target_seconds", "title", "premise")  # fmt: skip
    draft = ScriptDraft(script_id=old.script_id, slot=slot + 1, text=text,
                        changed_lines=[text.splitlines()[found["line"] - 1]],
                        **{k: getattr(old, k) for k in keep})  # fmt: skip
    db.add(draft)
    db.flush()
    project.script_draft_id = draft.id  # this video's words now; the script's others stay
    now = save_version(db, user, project, text, "owner_line")  # (commits)
    row = db.scalar(select(BreakdownVersion).where(BreakdownVersion.project_id == project.id)
                    .order_by(BreakdownVersion.id.desc()).limit(1))  # fmt: skip
    data = _with_line(row.data, found)
    new = BreakdownVersion(project_id=project.id, script_version=now.version, source="edit",
                           data={**data, **breakdown.carried_keys(row)}, created_by_id=user.id,
                           problems=breakdown.problems(db, project, text,
                                                       breakdown.Breakdown.model_validate(data),
                                                       data.get("song")))  # fmt: skip
    db.add(new)
    db.flush()  # a song part is carried on insert (song_breakdown._carry)
    cast_roles.carry_frames(db, project, row, new)
    cast_roles.carry_clips(db, project, row, new)
    for clip in found["clips"]:  # its clips stay on the old plan: made again (stale)
        if (r := _row(db, project, clip)) is not None:
            r.breakdown_id = row.id
    for r in db.scalars(
        select(ProjectClip).where(
            ProjectClip.breakdown_id == row.id, ProjectClip.project_id == project.id
        )
    ):
        if r.clip_id not in found["clips"]:
            r.breakdown_id = new.id  # every other clip and its takes stay as they are
    narrated = _narrated(db, project)
    if narrated:
        _read_again(db, user, project, draft)
    named = ", ".join(c.removeprefix("c") for c in found["clips"])
    some = f"clip{'s' if len(found['clips']) > 1 else ''} {named}"
    what = (f"The narration is being read again with it: use it once it's made, then make a "
            f"new take of {some} once its prompt is written again" if narrated else
            f"Make a new take of {some} once its prompt is written again")  # fmt: skip
    note = NOTE.format(n=found["line"], what=what)
    project.director_chat = [
        *(project.director_chat or []),
        {"text": note, "by": user.id, "at": utcnow().isoformat()},
    ]
    db.commit()
    if not narrated:  # its prompts are written again now, as after any edit (a narrated
        clip_prompts.follow(db, project, user)  # one's, once its new reading is timed)
    turn = director.start(db, user, project, approved=True)
    return {"run": turn.input[director.RUN]["id"], "version": now.version}


def _with_line(data: dict, found: dict) -> dict:
    """The plan with the changed line's words in its shots (a spoken shot's `line`)."""
    n = found["line"]
    scenes = [{**sc, "shots": [{**s, "line": _replaced(s["line"], found["old"], found["new"])}
                               if n in (s.get("script_lines") or []) and s.get("line") else s
                               for s in sc["shots"]]} for sc in data.get("scenes", [])]  # fmt: skip
    return {**data, "scenes": scenes}


def _read_again(db: Session, user: User, project: Project, draft: ScriptDraft) -> None:
    """A narrated video's narration with the new words, in the voice it has; nothing uses it
    until it's made and timed (the director uses it, and the shots follow it)."""
    from app import narration, song_takes
    from app.models.songs import SongTake

    was = db.get(SongTake, project.song_take_id) if project.song_take_id else None
    song_takes.make(db, user, draft, project, voice=(was.voice if was else "") or narration.VOICE)
    project.song_take_id = None  # the old words are never cut in again


def made(db: Session, mine: dict) -> tuple[str, str]:
    """How the press is going: its run's own state."""
    from app import director
    from app.models.jobs import Job

    rows = [j for j in db.scalars(select(Job).where(Job.input["step"].as_string() == director.STEP,
                                                    Job.input[director.RUN]["id"].as_string()
                                                    == mine["run"]))]  # fmt: skip
    if not rows or not any(j.input.get("ended") for j in rows):
        return "making", "A new version of the script: making only its clips again, then the cut."
    if director.delivered(rows):
        return "done", f"Done: version {mine.get('version')} of the script, and its cut."
    return "kept", "It stopped before the cut. Carry on in the chat."
