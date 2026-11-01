"""The director watches its cut (`watch_cut`, Reed: "watch and make those fixes if something
is off"): a free local listen of the finished video (its words and when, its shot changes)
picks up to FRAMES frames on those boundaries, then one Claude look at them with the words,
the script and the plan says what's off, clip by clip, each with a fix: redo with a note, pick
another take, mute a span, or keep. Priced "up to" on the director's own limit (a run's
spent()), never the video's budget. Advice for the director: Next-Server's tools act on it.

Findings are checked before the director reads them: a mute stays inside one clip and never
covers a script word (rule 19), and is given in that clip's take seconds, ready for
POST …/clips/{id}/mute; a pick names one of the clip's other takes. One that fails is dropped
and logged."""

import logging
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.models.projects import Project

log = logging.getLogger(__name__)

FRAMES, FEWEST = 24, 16  # frames a watch looks at: about one a second, 16 to 24
LISTEN, STEP, KIND = "cut_listen", "watch_cut", "check-claude"
NO_CUT = "Make the cut first."
FIXES = ("redo", "pick", "mute", "keep")


def frames_at(
    length: float, cuts: list[float], words: list[dict], spans: list[dict], count: int
) -> list[dict]:
    """Where a watch looks: on the cut's shot changes and where its lines start (a word after
    a pause), the most spread out, filled in evenly (take_frames.moments); each with its clip
    and what it sits on."""
    from app.take_frames import AFTER, moments

    starts = [w for n, w in enumerate(words) if n == 0 or w["start"] - words[n - 1]["end"] > 0.4]
    marks = {round(t + AFTER, 2): "a shot starts" for t in cuts}
    for w in starts:
        marks.setdefault(round(w["start"] + AFTER, 2), f'the word "{w["word"].strip()}"')
    return [{"t": t, "clip_id": clip_at(spans, t), "label": marks.get(t, "even spacing")}
            for t in moments(length, [m - AFTER for m in marks], count)]  # fmt: skip


def clip_at(spans: list[dict], t: float) -> str:
    """The clip of the cut at `t` seconds."""
    return next((s["clip_id"] for s in spans if s["start"] <= t < s["end"]),
                spans[-1]["clip_id"] if spans else "")  # fmt: skip


def spans_of(lengths: list[tuple[str, int, float]], total: float) -> list[dict]:
    """Where each clip sits in the cut ((clip_id, take_id, seconds) in order), scaled to the
    cut's own length (a re-encode can shift it a little)."""
    whole = sum(s for _, _, s in lengths) or 1.0
    at, out = 0.0, []
    for clip_id, take_id, seconds in lengths:
        end = at + seconds * total / whole
        out.append({"clip_id": clip_id, "take_id": take_id, "start": round(at, 2),
                    "end": round(end, 2)})  # fmt: skip
        at = end
    return out


def count_for(length: float) -> int:
    """About a frame a second, 16 to 24."""
    return max(FEWEST, min(FRAMES, round(length)))


def _cut(db: Session, project: Project) -> FinalVideo | None:
    return db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id)
                     .order_by(FinalVideo.id.desc()).limit(1))  # fmt: skip


def start(db: Session, user: User, project: Project, run: dict | None) -> str:
    """Watch the newest cut: its free listen is queued now, the look follows it."""
    from app.routes.jobs import enqueue

    video = _cut(db, project)
    if video is None:
        raise HTTPException(409, NO_CUT)
    clips = []
    for take_id in video.take_ids:
        take = db.get(ClipTake, take_id)
        row = db.get(ProjectClip, take.clip_id) if take else None
        if not take or not row:
            continue
        song = row.song_slice or {}
        clips.append({"clip_id": row.clip_id, "take_id": take.id,
                      "key": db.get(StoredFile, take.file_id).key,
                      "seconds": (song["end"] - song["start"]) if song else None})  # fmt: skip
    data = {"step": LISTEN, "project_id": project.id, "final_video_id": video.id,
            "video_key": db.get(StoredFile, video.file_id).key, "clips": clips,
            "director_run": run}  # fmt: skip
    enqueue(db, user, LISTEN, data, units=0, project=project, provider="local", prepaid=True)
    return "Watching the cut."


def heard_cut(db: Session, job: Job) -> None:
    """The listen is done (its words, frames and where each clip sits): the look is queued,
    on the director's own limit."""
    from app import plans, prompts
    from app.clip_prompts import newest
    from app.item_checks import latest, shown, verdict
    from app.routes.jobs import enqueue

    project = db.get(Project, job.project_id)
    out, user = job.output or {}, db.get(User, job.created_by_id)
    spans, frames = out.get("spans", []), out.get("frames", [])
    if not frames:
        raise RuntimeError("The cut had no frames to look at.")
    bd = newest(db, project)
    data = bd.data if bd else {"scenes": [], "clips": []}
    shots = {s["id"]: s for sc in data.get("scenes", []) for s in sc.get("shots", [])}
    ids = {c["id"]: c["shot_ids"] for c in data.get("clips", [])}
    cut = []
    for span in spans:
        mine = ProjectClip.project_id == project.id
        row = db.scalar(select(ProjectClip).where(mine, ProjectClip.clip_id == span["clip_id"]))
        takes = db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id)).all() if row else []
        others = [t for t in takes if t.id != span["take_id"]]
        seen = latest(db, "take", [t.id for t in others])
        heard = latest(db, "words", [t.id for t in others])
        cut.append({**{k: span[k] for k in ("clip_id", "start", "end", "take_id")},
                    "shots": [{"id": i, "action": shots[i].get("action", ""),
                               "line": shots[i].get("line")}
                              for i in ids.get(span["clip_id"], []) if i in shots],
                    "other_takes": [{"take_id": t.id, "number": t.number, "verdict": verdict(
                        [shown(db, seen.get(t.id)), shown(db, heard.get(t.id))])}
                        for t in others]})  # fmt: skip
    version = plans.script(db, project)
    plan = plans.current(db, project)
    labels = [(n, f"[Image{n}] {f['clip_id']} at {f['t']:.1f} s ({f['label']})")
              for n, f in enumerate(frames, 1)]  # fmt: skip
    text = prompts.watch_cut_input(
        version.text if version else "",
        _plan(plan, version),
        cut,
        out.get("words", []),
        labels,
        project.look or "house",
    )
    data = {"step": STEP, "project_id": project.id, "final_video_id": job.input["final_video_id"],
            "system": [prompts.system(STEP)], "prompt": text, "effort": "low", "max_tokens": 3000,
            "fit_images_to": 1024, "director_run": job.input.get("director_run"),
            "cut": cut, "words": out.get("words", []), "script": version.text if version else "",
            "files": {"reference_images": out.get("file_ids", [])}}  # fmt: skip
    enqueue(
        db,
        user,
        KIND,
        data,
        units=len(frames) + 1,
        project=project,
        provider="claude",
        prepaid=True,
    )  # "up to": a look a frame, and the words; the director's own limit


def _plan(plan: dict | None, version) -> str:
    from app import prompts
    from app.prompts.schemas import ScenePlan

    if not plan:
        return ""
    try:
        return prompts.plan_block(ScenePlan.model_validate(plan), version.text if version else "")
    except Exception:  # an old plan shape: the beats are only context
        return ""


def _bare(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def checked(answer: dict, cut: list[dict], words: list[dict], script: str) -> list[dict]:
    """The look's findings the director can act on: a mute inside one clip and over no
    script word, in that clip's take seconds; a pick of one of the clip's other takes."""
    spans = {c["clip_id"]: c for c in cut}
    said = set(_bare(script))
    out = []
    for f in (answer.get("findings") or [])[:6]:
        f = {**f, "fix": "pick" if f.get("fix") == "other_take" else f.get("fix")}
        span = spans.get(f.get("clip_id"))
        why = ""
        if span is None or f["fix"] not in FIXES:
            why = "names no clip of the cut" if span is None else f"fix {f['fix']!r}"
        elif f["fix"] == "mute":
            start, end = float(f["start"]), float(f["end"])
            over = [w for w in words if w["end"] > start and w["start"] < end]
            if not (span["start"] - 0.05 <= start < end <= span["end"] + 0.05):
                why = "a mute across clips"
            elif any(set(_bare(w["word"])) & said for w in over):
                why = "a mute over a script word"
            else:
                f["mute"] = [round(max(start - span["start"], 0), 2), round(end - span["start"], 2)]
        elif f["fix"] == "pick" and f.get("take_id") not in {
            t["take_id"] for t in span.get("other_takes", [])
        }:
            why = "a pick of a take that isn't the clip's"
        if why:
            log.info("watch_cut: dropped a finding (%s): %s", why, f.get("says"))
            continue
        f = {"mute": None, **f}
        if f["fix"] != "pick":
            f["take_id"] = None
        out.append(f)
    return out


def save(db: Session, job: Job) -> None:
    """The look's answer: its findings checked, kept with it for the director."""
    i = job.input
    found = checked(job.output or {}, i.get("cut", []), i.get("words", []), i.get("script", ""))
    job.output = {**(job.output or {}), "checked": found}


def watch_state(db: Session, project: Project) -> dict:
    """What the director reads as <video>.watch: the newest watch, and whether it's of the
    cut there is now."""
    from app.routes.project_clips import out_of_date

    newest = db.scalar(select(Job).where(Job.project_id == project.id,
                                         Job.input["step"].as_string().in_((LISTEN, STEP)))
                       .order_by(Job.id.desc()).limit(1))  # fmt: skip
    if newest is None:
        return {"state": "none"}
    video = _cut(db, project)
    for_cut = newest.input.get("final_video_id")
    current = bool(video and video.id == for_cut and project.id not in out_of_date(db, [project]))
    base = {"for_cut": for_cut, "current": current}
    if newest.status in (JobStatus.failed, JobStatus.cancelled):
        return {"state": "failed", **base}
    if newest.status != JobStatus.succeeded:
        return {"state": "watching", **base}
    if newest.input["step"] == LISTEN:  # heard, but its look was never queued (e.g. the cap)
        return {"state": "failed", **base}
    out = newest.output or {}
    return {"state": "done", **base, "lands": bool(out.get("lands")),
            "summary": out.get("summary", ""), "findings": out.get("checked", [])}  # fmt: skip
