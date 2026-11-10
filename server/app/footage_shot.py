"""A footage shot in UGC (Reed, 9 Nov; app/footage.py): a B-roll shot nobody speaks in may BE
one of the brand's real clips, from its in point to its out point, instead of being made
(`checked`): its take is cut from the clip on our server, free (`settle`), laid over or under
the voice like any B-roll (cut.py), shown once in the video, never watched or remade. Rule 13
(Reed, 9 Nov): it stops screenshots and stills being dropped onto the screen out of context;
real B-roll footage used as a B-roll shot in UGC, within the story, is allowed. A clip that
can't be one now (the video isn't UGC; the clip was deleted, marked a competitor's or is named
as animation) is taken out of the plan, with Advice, whenever the clips are written, the look
is switched or the cut is made (QA on #1513 and #1518)."""

import math
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import footage_rank, looks
from app.footage import KEY, live, ugc
from app.models.clips import ClipTake, ProjectClip
from app.models.files import MediaUpload, StoredFile
from app.models.jobs import Job, JobStatus
from app.models.projects import Project

TAKE = "footage_take"  # a footage shot's take, cut from its clip (the local lane, free)
SHORTEST = 0.5  # seconds a footage shot is at least
NOT_MADE = ("This shot is the brand's real footage: it's cut from the clip, never made. Change "
            "its in and out points in the plan, or take the footage off the shot.")  # fmt: skip
NOT_UGC = "real footage is a shot only in UGC"
DROPPED = ("Some real footage shots can't be used now (the plan's Advice says why), so they're "
           "made like the rest: write their clip prompts and make their takes, then make the "
           "video.")  # fmt: skip
WATCHED = ("Real footage isn't remade. If this stretch doesn't show its line, tell the director "
           "which part of the clip to use, and the plan picks it again.")  # fmt: skip


def _talks(shot) -> bool:
    return bool(shot.line or shot.speaker or getattr(shot, "sung", False))


def _why_not(db: Session, project: Project, use_id: str, have: dict[str, MediaUpload]) -> str:
    """Why a clip can't be a footage shot now, or "" (`have`: the brand's live footage)."""
    row = have.get(use_id)
    return (NOT_UGC if not ugc(project)
            else "that clip isn't in the brand's footage" if row is None
            else "that clip is a competitor's product" if row.competitor
            else "that clip is animated, not real" if footage_rank.animated(db, row)
            else "")  # fmt: skip


def _have(db: Session, project: Project) -> dict[str, MediaUpload]:
    return {f"{KEY}{r.id}": r for r in live(db, project.brand_id)}


def checked(db: Session, project: Project, bd, timed: bool = False):
    """Each footage shot as it can be used (free, in code; each change said as Advice): only
    in UGC, only on a B-roll shot nobody speaks in that is a clip of its own, only a clip of the
    brand's (never a competitor's, nor one that says it's animated), each once in the video;
    its stretch kept inside the clip. It shows the real thing: no cast sheet or screen goes with
    it. Not `timed`: the shot is as long as its stretch.
    `timed` (a narration's or a song's clock sets the shot's seconds): the stretch is fitted to
    them, from its in point, moved back to stay inside the clip; a clip shorter than the shot
    is never held on a frozen frame: the shot is made instead (QA on #1513)."""
    shots = [s for scene in bd.scenes for s in scene.shots]
    if not any(s.footage for s in shots):
        return bd, []
    clips = {sid: c for c in bd.clips for sid in c.shot_ids}
    have = _have(db, project)
    seen, notes = set(), []
    for s in (s for s in shots if s.footage):
        use, clip = s.footage, clips.get(s.id)
        length = (have[use.id].seconds or 0) if use.id in have else 0
        why = _why_not(db, project, use.id, have) or (
               "someone speaks in it" if _talks(s)
               else f"{use.id} is already shown in this video" if use.id in seen
               else "it shares its clip with other shots" if clip and len(clip.shot_ids) > 1
               else f"the clip is {length:.1f} s, shorter than the shot's {s.seconds:.1f} s"
               if timed and length < s.seconds - 0.05
               else "")  # fmt: skip
        if why:
            s.footage = None
            notes.append(f"Advice: Shot {s.id} is made, not real footage: {why}.")
            continue
        seen.add(use.id)
        start = round(min(max(use.start, 0.0), max(length - SHORTEST, 0.0)), 2)
        end = round(min(max(use.end, start + SHORTEST), length), 2)
        if timed:  # exactly the shot's time on its clock, inside the clip
            start = round(max(0.0, min(start, length - s.seconds)), 2)
            end = round(min(start + s.seconds, length), 2)
        s.footage = use.model_copy(update={"start": start, "end": end})
        s.character_ids, s.screen_ids, s.screen_figure = [], [], None
        if not timed:
            s.seconds = round(end - start, 1)
            if clip:
                clip.seconds = max(1, math.ceil(end - start - 0.01))
    return bd, notes


def uses(data: dict) -> dict[str, dict]:
    """The plan's footage clips: clip id -> its one shot's footage ({id, start, end, sound})."""
    shots = {s["id"]: s for sc in data.get("scenes", []) for s in sc.get("shots", [])}
    out = {}
    for c in data.get("clips", []):
        mine = [shots[i] for i in c.get("shot_ids", []) if i in shots]
        if len(mine) == 1 and mine[0].get("footage"):
            out[c["id"]] = mine[0]["footage"]
    return out


def of_clip(db: Session, row: ProjectClip) -> dict | None:
    """The footage a clip's plan shows, or None (a clip that's made)."""
    from app.models.breakdowns import BreakdownVersion

    plan = db.get(BreakdownVersion, row.breakdown_id) if row.breakdown_id else None
    return uses(plan.data).get(row.clip_id) if plan else None


def is_footage(take: ClipTake | None) -> bool:
    return bool(take and (take.made_with or {}).get("footage"))


HEAD = "Real footage from the brand's library"  # a footage clip's prompt: it has no other


def _prompt(row: MediaUpload, use: dict) -> str:
    return (f"{HEAD} ({KEY}{row.id}, {use['start']:.1f}–"
            f"{use['end']:.1f} s{'' if use.get('sound') else ', muted'}): "
            f"{row.description.strip()}")  # fmt: skip


def settle(db: Session, project: Project, user_id: int | None = None, first: bool = True) -> bool:
    """The newest plan's footage clips, free: each has its row (the plan's, so its prompt is
    never written) and its take, cut from the clip on our server (`TAKE`), picked once it's
    made; one cut for this use already is picked again. A clip the plan now makes stops using
    a footage take, and one that never had a prompt of its own goes (its prompt is written and
    its take made like any clip's). Not `first`: only once the video's clips are written
    (their prompts come first, as the director asks for them). A footage shot that can't be
    one now (`_why_not`: its B-roll look changed, or its clip was deleted, marked a
    competitor's or named as animation) is taken out of the plan (True: some were), whenever
    its clips are written, its look switched or its cut made (QA on #1513 and #1518)."""
    from sqlalchemy import delete

    from app.clip_prompts import newest

    bd = newest(db, project)
    dropped = bd is not None and _unplan(db, project, bd)
    rows = {r.clip_id: r for r in db.scalars(select(ProjectClip).where(
        ProjectClip.project_id == project.id))}  # fmt: skip
    if bd is None or not (first or rows):
        return dropped
    wanted = uses(bd.data)
    for clip_id, row in rows.items():
        if clip_id in wanted:
            continue
        if (row.prompt or "").startswith(HEAD):  # never written: written now, as any clip
            row.picked_take_id = None
            db.flush()
            db.execute(delete(ClipTake).where(ClipTake.clip_id == row.id))
            db.delete(row)
        elif is_footage(db.get(ClipTake, row.picked_take_id or 0)):
            row.picked_take_id = row.file_id = None
    for clip_id, use in wanted.items():
        source = db.get(MediaUpload, int(use["id"].removeprefix(KEY)))
        row = rows.get(clip_id)
        if row is None:
            row = ProjectClip(project_id=project.id, clip_id=clip_id, references=[], prompt="")
            db.add(row)
        row.breakdown_id, row.seconds = bd.id, max(1, math.ceil(use["end"] - use["start"] - 0.01))
        row.prompt, row.references, row.problems, row.kept = _prompt(source, use), [], [], []
        row.job_id = None
        db.flush()
        takes = db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id)).all()
        same = next((t for t in takes if (t.made_with or {}).get("footage") == use), None)
        if same is not None:
            row.picked_take_id, row.file_id = same.id, same.file_id
            continue
        if _cutting(db, row.id, use):
            continue
        db.add(Job(workspace_id=project.workspace_id, created_by_id=user_id or
                   project.created_by_id, kind=TAKE, provider="local", credits=0,
                   status=JobStatus.queued, project_id=project.id, brand_id=project.brand_id,
                   input={"step": TAKE, "project_id": project.id, "project_clip_id": row.id,
                          "footage": use, "video_key": db.get(StoredFile, source.file_id).key,
                          "clip_prompt": row.prompt}))  # fmt: skip
    db.flush()
    return dropped


def _unplan(db: Session, project: Project, bd) -> bool:
    """The plan's footage shots that can't be one now made like the rest, each said as Advice
    on it. True when it took any out."""
    from sqlalchemy.orm.attributes import flag_modified

    shots = [s for sc in bd.data.get("scenes", []) for s in sc.get("shots", [])
             if s.get("footage")]  # fmt: skip
    have, notes = _have(db, project) if shots else {}, []
    for shot in shots:
        if why := _why_not(db, project, shot["footage"].get("id"), have):
            del shot["footage"]
            notes.append(f"Advice: Shot {shot['id']} is made, not real footage: {why}.")
    if notes:
        bd.problems = [*(bd.problems or []), *notes]
        flag_modified(bd, "data")
    return bool(notes)


def _cutting(db: Session, row_id: int, use: dict) -> bool:
    waiting = db.scalars(select(Job).where(Job.kind == TAKE, Job.status.in_(
        (JobStatus.queued, JobStatus.running))))  # fmt: skip
    return any(j.input.get("project_clip_id") == row_id and j.input.get("footage") == use
               for j in waiting)  # fmt: skip


def save_take(db: Session, job: Job) -> None:
    """The cut is made: a take of its clip, picked, as made from the footage (no watch: real
    footage is never checked or remade)."""
    from app.clip_takes import pick

    row = db.get(ProjectClip, job.input["project_clip_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if row is None or not file_ids or of_clip(db, row) != job.input["footage"]:
        return  # the plan moved on while it was cut
    count = len(db.scalars(select(ClipTake.id).where(ClipTake.clip_id == row.id)).all())
    take = ClipTake(clip_id=row.id, number=count + 1, job_id=job.id, file_id=file_ids[0],
                    prompt=row.prompt, look=looks.drawn(db.get(Project, row.project_id)),
                    made_with={"footage": job.input["footage"]})  # fmt: skip
    db.add(take)
    db.flush()
    pick(row, take)


def cut(video: bytes, start: float, end: float, sound: bool, folder: Path) -> Path:
    """The stretch of a clip from `start` to `end`, as an H.264 MP4 (its sound only with
    `sound`): the footage shot's take."""
    src, out = folder / "footage.mp4", folder / "cut.mp4"
    src.write_bytes(video)
    audio = ["-c:a", "aac", "-b:a", "128k"] if sound else ["-an"]
    subprocess.run(  # noqa: S603
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", str(src),  # noqa: S607
         "-t", f"{end - start:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", *audio,
         "-movflags", "+faststart", str(out)], timeout=120, check=True)  # fmt: skip
    src.unlink()
    return out
