"""One live progress record per director run (v6 piece C: boards S3-03, S3-04, S3-08, S3-11,
S3-12, S3-13, S6-01, S6-04, S6-05, P-04, P-05, P-10). It's read from what the run made, in
the same few queries however many clips there are (118 in a long Movie), so the video page
can poll it. It replaces the chat's one row a turn: the thread has one item a run
(`thread_items`) with this record behind it, and each delivery's note (app/delivery). Plain
words; money is dollars to the owner and credits to everyone else."""

import math
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from statistics import median
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import asks, model_map
from app.breakdown_fix import too_long
from app.models.accounts import User
from app.models.brands import Brand
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import WAITING, Job, JobStatus
from app.models.projects import Project
from app.models.seen import TakeSeen
from app.models.storyboards import StoryboardFrame
from app.prompts.schemas import Breakdown

TYPICAL_TAKE = 180  # seconds a take takes, until this workspace has made some
HELD = JobStatus.needs_owner_approval
STOPPED_BY = "stopped_by"  # on the turn a person's Stop ended: who (and "stopped_at": when)
RUN = "director_run"  # a turn's run (director.RUN)
WATCHED = "The watch found: "  # a remake's why when the watch of the cut asked for it
DONE = ("done", "redone", "text", "flagged")  # a clip with a take in hand
ORDER = ("read", "plan", "cast", "voice", "stills", "prompts", "takes", "watching", "host", "cut")
PHASES = {"treatment": "plan", "plan": "plan", "make_looks": "cast", "song": "voice",
          "narration": "voice", "storyboard": "stills", "stills": "stills",
          "review_stills": "stills", "redraw_still": "stills", "clip_prompts": "prompts",
          "split_clip": "plan",
          "make_take": "takes", "pick_take": "takes", "splice_word": "takes", "mute": "takes",
          "add_sound": "takes", "host": "host", "final_cut": "cut", "watch_cut": "cut",
          "deliver": "cut"}  # fmt: skip  # the step each of the director's tools works on


def money(credits: Decimal | float, owner: bool) -> str:
    """A price as the viewer reads it: "$0.32" to the owner, "4 credits" to anyone else;
    rounded up, never below what it charges (rule 36)."""
    from app.credits import price
    from app.models.credits import USD_PER_CREDIT

    if owner:
        return f"${math.ceil(Decimal(str(credits)) * USD_PER_CREDIT * 100) / 100:.2f}"
    n = price(Decimal(str(credits)))
    return f"{n} credit" if n == 1 else f"{n} credits"


def said(text: str) -> str:
    """Plain words as people read them: "clip 3", never "c3", nor a finding's "c3: " head."""
    from app.director import named

    return named(re.sub(r"^c\d+: ", "", (text or "").strip()))


def runs(db: Session, project: Project) -> dict[str, list[Job]]:
    """Every director run on the video, oldest first: its turns in order."""
    rows = db.scalars(select(Job).where(Job.project_id == project.id,
                                        Job.input["step"].as_string() == "director")
                      .order_by(Job.id)).all()  # fmt: skip
    out: dict[str, list[Job]] = {}
    for j in rows:
        out.setdefault(j.input[RUN]["id"], []).append(j)
    return out


def ending(turns: list[Job]) -> tuple[str, str]:
    """(how a run ended: "" while it goes on, delivered, stopped (a person's Stop, or the
    owner declined its held turn), or needs_fix; the reason it gave)."""
    why = next((j.input["ended"] for j in reversed(turns) if j.input.get("ended")), None)
    if why is None and turns[-1].status != JobStatus.cancelled:
        return "", ""
    if any(j.input.get("result") == "Delivered." for j in turns):
        return "delivered", why or ""
    if any(j.input.get(STOPPED_BY) for j in turns):
        return "stopped", why or "Stopped."
    if turns[-1].input.get("declined"):  # the owner said no to its held turn: not a fault
        return "stopped", f"The owner declined: {turns[-1].error}".rstrip(": ")
    if turns[-1].input.get("withdrawn") or turns[-1].status == JobStatus.cancelled:
        return "stopped", "Withdrawn."  # its held turn taken back before the OK
    return "needs_fix", why or "Stopped."


def _end_at(turns: list[Job]) -> datetime:
    return turns[-1].finished_at or turns[-1].created_at


def _took(turns: list[Job]) -> str:
    took = (_end_at(turns) - turns[0].created_at).total_seconds()
    return f"Made in {max(1, round(took / 60))} min"


def _n(n: int, what: str) -> str:
    return f"{n} {what}" + ("" if n == 1 else "s")


def watched(turns: list[Job]) -> dict[str, str]:
    """What the watch of the cut found on each clip the run remade for it (its why)."""
    said = [j.output for j in turns if (j.output or {}).get("tool") == "make_take"]
    return {o["clip_id"]: o["why"].removeprefix(WATCHED) for o in said
            if (o.get("why") or "").startswith(WATCHED)}  # fmt: skip


def _found(row: ItemCheck | None) -> list[dict]:
    """A take check's findings people haven't set aside (Looks fine)."""
    gone = {d["index"] for d in (row.dismissed or [])} if row else set()
    return [f for i, f in enumerate(row.findings or []) if i not in gone] if row else []


class _Video:
    """Everything the record reads, in a fixed number of queries however many clips."""

    def __init__(self, db: Session, project: Project, viewer: User | None, turns: list[Job]):
        from app.breakdown import video_model
        from app.clip_prompts import newest

        self.project, bd = project, newest(db, project)
        self.data = bd.data if bd else {}
        self.problems = (bd.problems or []) if bd else []  # "clip c4: 115 s is outside 4–12 s"
        self.clips = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)
                                .order_by(ProjectClip.id)).all()  # fmt: skip
        # a planned clip with no prompt yet is to do, once clips are written (before: Planning)
        have = {c.clip_id for c in self.clips}
        self.clips += [SimpleNamespace(id=None, clip_id=c["id"], seconds=c["seconds"],
                                       picked_take_id=None) for c in self.data.get("clips", [])
                       if have and c["id"] not in have]  # fmt: skip
        ids = [c.id for c in self.clips if c.id]
        self.takes: dict[int, list[ClipTake]] = defaultdict(list)
        for t in db.scalars(select(ClipTake).where(ClipTake.clip_id.in_(ids))
                            .order_by(ClipTake.number)):  # fmt: skip
            self.takes[t.clip_id].append(t)
        tids = [t.id for ts in self.takes.values() for t in ts]
        self.checks: dict[int, dict[str, ItemCheck]] = defaultdict(dict)  # the newest of each
        for c in db.scalars(select(ItemCheck).where(ItemCheck.target.in_(("take", "words")),
                                                    ItemCheck.target_id.in_(tids))
                            .order_by(ItemCheck.id)):  # fmt: skip
            self.checks[c.target_id][c.target] = c
        self.asked = watched(turns)
        self.jobs: dict[int, list[Job]] = defaultdict(list)  # each clip's takes being made, …
        self.made_by: dict[int, Job] = {}
        for j in db.scalars(select(Job).where(Job.project_id == project.id, Job.kind == "video")
                            .order_by(Job.id)):  # fmt: skip
            self.made_by[j.id] = j
            if clip := j.input.get("project_clip_id"):
                self.jobs[clip].append(j)
        frames = db.scalars(select(StoryboardFrame).where(
            StoryboardFrame.project_id == project.id,
            StoryboardFrame.breakdown_id == (bd.id if bd else None))).all()  # fmt: skip
        self.stills, self.drawn = len(frames), sum(bool(f.file_id) for f in frames)
        self.frames: dict[str, int] = {}  # each clip's first drawn still: its frame
        for f in sorted(frames, key=lambda f: [int(x) for x in re.findall(r"\d+", f.shot_id)]):
            if f.file_id:
                self.frames.setdefault(f.clip_id, f.file_id)
        mine = TakeSeen.user_id == (viewer.id if viewer else 0)
        seen = select(TakeSeen.take_id).where(mine, TakeSeen.take_id.in_(tids))
        self.seen = set(db.scalars(seen))
        spans = db.execute(select(Job.started_at, Job.finished_at).where(
            Job.workspace_id == project.workspace_id, Job.kind == "video",
            Job.status == JobStatus.succeeded, Job.started_at.is_not(None))
            .order_by(Job.id.desc()).limit(20)).all()  # fmt: skip
        took = [(b - a).total_seconds() for a, b in spans if b and b > a]
        self.typical = median(took) if took else TYPICAL_TAKE
        self.engine = video_model(project)
        self.model = self.engine.name
        shots = {x["id"]: x for s in self.data.get("scenes", []) for x in s.get("shots", [])}
        self.shots = {c["id"]: [shots[i] for i in c["shot_ids"] if i in shots]
                      for c in self.data.get("clips", [])}  # fmt: skip

    def scenes(self) -> list[tuple[int, str]]:
        """(id, name) in order: the plan's part ("Hook"), else the scene's heading."""
        parts = {s.get("id"): s.get("part") for s in (self.project.plan or {}).get("scenes", [])}
        return [(s["id"], parts.get(s["id"]) or s.get("heading") or f"Scene {s['id']}")
                for s in self.data.get("scenes", [])]  # fmt: skip

    def pk(self, clip_id: str) -> int | None:
        return next((r.id for r in self.clips if r.clip_id == clip_id), None)


def _model(take: ClipTake | None, fallback: str) -> str:
    """The model a take was made on, else `fallback` (the video's, read once a record)."""
    from app.catalogue import catalogue

    said = (take.made_with or {}) if take else {}
    made = catalogue().get(said.get("model") or said.get("video_model") or "")  # VS1's key
    return made.name if made else fallback


def cell(video: _Video, row: ProjectClip, now: datetime, owner: bool) -> dict:
    """One clip as the filmstrip and the Clips list read it: its state, frame and line.
    `changed`: the director made its take again (its watch, or a note); `watched`: this person
    has watched that take since; `found`: its watch found something on one of its takes."""
    from app.credits import WAIT_OK

    takes, jobs = video.takes.get(row.id, []), video.jobs.get(row.id, [])
    held = next((j for j in jobs if j.status == HELD), None)
    making = next((j for j in jobs if j.status in WAITING and j.status != HELD), None)
    picked = next((t for t in takes if t.id == row.picked_take_id), takes[-1] if takes else None)
    last = next((j for j in reversed(jobs) if j.status != JobStatus.cancelled), None)
    found = lambda ts: [f for t in ts for c in video.checks[t.id].values() for f in _found(c)]  # noqa: E731
    now_found = found([picked]) if picked else []
    before = found([t for t in takes if picked and t.number < picked.number])
    job = video.made_by.get(picked.job_id) if picked else None
    changed = bool(picked and picked.number > 1 and job and job.input.get("by_director"))
    shots = video.shots.get(row.clip_id) or [{}]
    scene = str(shots[0].get("id", "")).split(".")[0]
    out = {"clip_id": row.clip_id, "number": int(row.clip_id.removeprefix("c") or 0),
           "scene": int(scene) if scene.isdigit() else 0, "seconds": row.seconds,
           "label": (shots[0].get("action") or "").split(". ")[0].strip().rstrip("."),
           "model": _model(picked, model_map.own_name(row) or video.model),
           "frame_file_id": video.frames.get(row.clip_id),
           "take_id": picked.id if picked else None, "state": "done", "note": "",
           "percent": None, "minutes_left": None, "credits": None, "changed": changed,
           "watched": bool(picked and picked.id in video.seen),
           "found": bool(found(takes))}  # fmt: skip
    if held is not None:  # its take waits for the owner's OK (past the budget)
        why = (held.input.get("held") or "").removeprefix(WAIT_OK)
        return {**out, "state": "waiting", "note": why[:1].upper() + why[1:],
                "credits": money(held.credits, owner)}  # fmt: skip
    if making is not None:
        ran = (now - making.started_at).total_seconds() if making.started_at else 0
        left = max(0, video.typical - ran)
        line = (said((now_found or [{}])[0].get("text", "")) if takes
                else "The still is ready; the take is being made" if out["frame_file_id"]
                else "The take is being made")  # fmt: skip
        return {**out, "state": "making", "note": line,
                "minutes_left": max(1, math.ceil(left / 60)),
                "percent": min(95, round(100 * ran / video.typical))}  # fmt: skip
    if last and last.status == JobStatus.failed and (not picked or last.id > picked.job_id):
        why = (last.error or "It didn't finish").rstrip(".")
        return {**out, "state": "failed", "note": f"{why}. Nothing was charged.",
                "credits": money(last.credits, owner)}  # fmt: skip
    if row.clip_id in too_long(video.problems):  # longer than the model makes: never sent
        m = video.engine
        return {**out, "state": "too_long",
                "note": f"{m.name} makes at most {m.duration.max} s a clip"}  # fmt: skip
    if picked is None:
        return {**out, "state": "todo"}
    if now_found:  # the take in use still has what its watch found: a person decides
        return {**out, "state": "flagged", "note": said(now_found[0].get("text", ""))}
    if changed:  # the watch of the take, or of the cut, found it; or a person asked
        text = any(f.get("kind") == "text" for f in before)  # words in the picture, remade
        why = before[0].get("text", "") if before else video.asked.get(row.clip_id, "")
        return {**out, "state": "text" if text else "redone", "note": said(why)}
    return out


def steps(db: Session, video: _Video, turns: list[Job], cells: list[dict], how: str,
          held: bool, owner: bool) -> list[dict]:  # fmt: skip
    """The step list in plain words, each done, now, todo, wait (for an OK) or bad (where it
    stopped). The step the run's newest tool works on is now (a remake after the cut: the
    takes again); the ones before it are done, the ones after it still to do."""
    from app import director_song, guides, host
    from app.cast_roles import video_slots

    project = video.project
    tools = [(j.output or {}).get("tool") for j in turns if "result" in j.input]
    at = next((ORDER.index(PHASES[t]) for t in reversed(tools) if t in PHASES), 0)  # newest
    try:
        style = guides.style(project.look)["name"]
    except ValueError:
        style = project.look
    total, made = len(cells), sum(c["state"] in DONE for c in cells)
    seconds, scenes = sum(c["seconds"] for c in cells), len({c["scene"] for c in cells})
    words = {"read": f"Read the script, the {style} guide and "
                     f"{db.get(Brand, project.brand_id).name}’s brand kit",
             "plan": f"Treatment and plan: {_n(scenes, 'scene')}, {_n(total, 'clip')}, "
                     f"about {seconds} s"
                     if total else "Treatment and plan"}  # fmt: skip
    roles = [s.role for s in video_slots(db, project)]
    cast = ", ".join(roles[:-1]) + f" and {roles[-1]}" if len(roles) > 1 else "".join(roles)
    if roles:
        words["cast"] = f"Cast: {cast}"
    if director_song.kind(db, project):
        audio = director_song.state(db, project) or {"takes": []}
        used = next((t for t in audio["takes"] if t["used"]), None) or {}
        long = f": {used['seconds']:.1f} s" if used.get("seconds") else ""
        right = used.get("timed") and not used.get("missing") and not used.get("misheard")
        words["voice"] = (f"Song{long}" + (", every lyric heard" if right else "")
                          if "style" in audio else f"Voice track{long}"
                          + (", words checked against the script" if right else ""))  # fmt: skip
    redraws = sum((turns[-1].input.get(RUN) or {}).get("redraws", {}).values())
    words["stills"] = (f"Stills: {video.drawn} drawn" if video.drawn else "Stills") + (
        f", {redraws} redrawn" if redraws else "")  # fmt: skip
    hosted, model = host.on(db, project), video.model
    words["prompts"] = ("Clip prompts written · " + (f"B-roll on {model}, host on P-Video"
                        if hosted else f"on {model}")) if total else "Clip prompts"  # fmt: skip
    words["takes"] = f"Making takes: {made} of {total}" if made < total else f"Takes: {total} made"
    if watching := _watching(db, video, cells, owner):
        words["watching"] = watching[0]
    if hosted:
        words["host"] = f"Lay {cast or 'the presenter'} over the B-roll"
    words["cut"] = "Watch the whole cut, then deliver"
    first = next((c for c in cells if c["state"] == "making"), None)
    subs = {"stills": f"{video.drawn} of {video.stills} drawn" if video.stills else "",
            "takes": f"Clip {first['number']} · scene {first['scene']} · {first['seconds']} s · "
                     f"about {first['minutes_left']} min" if first else "",
            "watching": watching[1] if watching else ""}  # fmt: skip
    out = []
    for key in (k for k in ORDER if k in words):
        n = ORDER.index(key)
        state = "done" if how == "delivered" or n < at else "now" if n == at and not how else "todo"
        if key == "watching" and first and not how:
            state = "now"  # it watches each take as it lands, while takes are made
        if n == at and how:
            state = {"needs_fix": "bad", "stopped": "todo"}.get(how, state)
        if n == at and held and not how:
            state = "wait"
        out.append({"key": key, "state": state, "text": words[key],
                    "sub": subs.get(key, "") if state in ("now", "wait") else ""})  # fmt: skip
    return out


def _watching(db: Session, video: _Video, cells: list[dict],
              owner: bool) -> tuple[str, str] | None:  # fmt: skip
    """("Watching each take as it lands: 12 watched, 1 redone", the newest it acted on)."""
    rows = [c["take"] for c in video.checks.values() if "take" in c]
    if not rows:
        return None
    text = (f"Watching each take as it lands: {sum(r.status == 'done' for r in rows)} watched, "
            f"{sum(c['changed'] for c in cells)} redone")  # fmt: skip
    acted = [c for c in cells if c["found"] and c["note"]]
    if not acted:
        return text, ""
    c = acted[-1]
    job = next((j for j in video.jobs.get(video.pk(c["clip_id"]), []) if j.status in WAITING),
               None) if c["state"] == "making" else None  # fmt: skip
    if job is not None:  # its "up to": the take and the watch that rides along (rule 36)
        from app import take_watch

        row = next(r for r in video.clips if r.clip_id == c["clip_id"])
        price = job.credits + take_watch.rides(db, video.project, row)
    tail = f" Remaking it ({money(price, owner)})." if job else ""
    return text, f"Clip {c['number']}: {c['note'].rstrip('.')}.{tail}"


def price_of(db: Session, project: Project) -> Decimal:
    """The run's "up to", as the press that started it showed it: a freestyle's approved
    price; a video's run price (rule 34: its plan, 2 remakes a clip, the director's limit)."""
    from app.credits import budget
    from app.models.script_library import ScriptDraft
    from app.routes.estimate import run_price

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    return budget(db, project) if project.hidden or draft is None else run_price(db, draft, project)


def run_up_to(db: Session, project: Project) -> Decimal:
    """The video's "up to" once a run is under way or delivered: what every Make it approved
    (`asks.approved_total`, board S3-12), so the header, the start card, the run's card and
    its note say one figure on every run; before any Make it, the price a new run would show.
    A freestyle's video, hidden or in its brand, reads its sends' approved total, as its
    header does."""
    from app import asks
    from app.credits import approved
    from app.models.freestyles import Freestyle

    fs = db.scalar(select(Freestyle).where(Freestyle.project_id == project.id))
    if fs is not None and fs.up_to is not None:
        return approved(db, fs)
    if project.hidden:
        return price_of(db, project)
    got = asks.approved_total(db, project)
    return got if got is not None else price_of(db, project)


def spent(db: Session, project: Project) -> tuple[Decimal, Decimal]:
    """(what the video has charged so far, its "up to"), in credits, as its header says them
    (board S3-12: the whole video's figures, one for the header, the run card and the note):
    every counted job on it, and `run_up_to` never below that, rounded up as the header
    rounds it."""
    from app import ideas

    used = ideas.facts(db, [project]).used.get(project.id, Decimal(0))
    return used, ideas._up(max(run_up_to(db, project), used))


def dollars(credits: Decimal) -> float:
    """Credits as the owner reads them, in dollars at the header's rate (`ideas._money`)."""
    from app.models.credits import USD_PER_CREDIT

    return float(round(credits * USD_PER_CREDIT * 100) / 100)


def _changes(video: _Video, turns: list[Job], since: datetime) -> str:
    """A revising run's changes (S3-12, "1 of 2 changes"): each take it makes again of a clip
    that had one before it began, and each free fix (a pick, a mute, a splice)."""
    total = done = 0
    for row in video.clips:
        if any(t.created_at < since for t in video.takes.get(row.id, [])):
            for j in video.jobs.get(row.id, []):
                if j.created_at >= since and j.status != JobStatus.cancelled:
                    total, done = total + 1, done + (j.status == JobStatus.succeeded)
    for j in turns:
        if (j.output or {}).get("tool") in ("pick_take", "mute", "splice_word") and not (
            j.input.get("result") or "Refused").startswith("Refused"):  # fmt: skip
            total, done = total + 1, done + 1
    return f"{done} of {_n(total, 'change')}"


def record(db: Session, project: Project, viewer: User | None) -> dict | None:
    """The newest run's progress record, as `ProgressOut` reads it; None before any run."""
    from app.auth import user_name
    from app.credits import WAIT_OK
    from app.db import utcnow

    every = runs(db, project)
    if not every:
        return None
    run_id, turns = list(every.items())[-1]
    owner, (how, why) = bool(viewer and viewer.is_owner), ending(turns)
    now, start = utcnow(), turns[0].created_at
    video = _Video(db, project, viewer, turns)
    cells = [cell(video, r, now, owner) for r in video.clips]
    held = select(Job).where(
        Job.project_id == project.id, Job.status == HELD, Job.input["ask_id"].as_integer().is_(None)
    )  # an option: its card
    held = held.order_by(Job.id)
    holds = None if how else db.scalar(held.limit(1))
    revising = any(r != run_id and ending(t)[0] == "delivered" for r, t in every.items())
    scenes = [{"id": sid, "name": name, "clips": [c for c in cells if c["scene"] == sid]}
              for sid, name in video.scenes()]  # fmt: skip
    other = [c for c in cells if c["scene"] not in {s["id"] for s in scenes}]
    scenes += [{"id": 0, "name": "", "clips": other}] if other else []  # in no scene (yet)
    for s in scenes:
        s.update(total=len(s["clips"]), done=sum(c["state"] in DONE for c in s["clips"]))
    at = next((n for n, s in enumerate(scenes, 1) if s["done"] < s["total"]), len(scenes))
    total, made = len(cells), sum(c["state"] in DONE for c in cells)
    redone = sum(c["changed"] for c in cells)
    charged, up_to = spent(db, project)
    if how == "delivered":
        head = ("delivered", _took(turns), _n(total, "clip") + (
            f" · {redone} redone after watching" if redone else ""), "done")  # fmt: skip
    elif how:
        long = next((c for c in cells if c["state"] == "too_long"), None)
        bad = (_blamed(cells, why) or (long if "makes at most" in why else None)
               if how == "needs_fix" else None)  # fmt: skip
        plain = how == "needs_fix" or why == "Stopped."
        head = (how, f"Stopped at clip {bad['number']}" if bad else "Stopped",
                f"{made} of {total} clips made" if plain else said(why),
                "bad" if how == "needs_fix" else "stop")  # fmt: skip
    elif (
        holds is not None
        and holds.input.get(asks.START)
        and viewer
        and asks.may_start(db, viewer, project)
    ):  # its start card, theirs to press (S3-02)
        head = ("waiting", "Ready to make", "No generation started: press Make it", "wait")
    elif holds is not None:
        why = (holds.input.get("held") or "").removeprefix(WAIT_OK).rstrip(".")
        head = ("waiting", "Waiting for your OK" if owner else "Waiting for the owner's OK",
                why, "wait")  # fmt: skip
    elif revising:
        head = ("revising", "Revising", _changes(video, turns, start), "now")
    elif made < total:
        head = ("working", "Making the clips", f"{made} of {total} · scene {at} of {len(scenes)}",
                "now")  # fmt: skip
    else:
        head = ("working", "Cutting it together" if total else "Planning",
                f"{total} clips made" if total else "", "now")  # fmt: skip
    again = price_of(db, project)  # carrying on is a new run: its whole "up to" (rule 36)
    for c in cells:  # a press's price as it charges: the take with the check that rides along
        if c["state"] in ("waiting", "failed"):
            c["credits"] = money(_take_price(db, video, c), owner)
    out = {"run": run_id, "status": head[0], "title": head[1], "sub": head[2], "tone": head[3],
           "started_at": start, "ended_at": _end_at(turns) if how else None, "clips": total,
           "made": made, "redone": redone, "scene_at": at, "scenes": scenes,
           "counts": {"all": total, "redone": redone,
                      "flagged": sum(c["state"] == "flagged" for c in cells),
                      "needs_you": sum(c["state"] in ("flagged", "waiting", "failed")
                                       for c in cells)},
           "minutes_left": None if how else _left(video, cells, start, now),
           "steps": steps(db, video, turns, cells, how, holds is not None, owner),
           "spent": float(charged), "up_to": float(up_to),
           "spent_usd": dollars(charged) if owner else None,
           "changed": [{k: c[k] for k in ("clip_id", "number", "take_id", "frame_file_id",
                                          "watched")} for c in cells if c["changed"]],
           "stopped": None, "failed": None}  # fmt: skip
    by = next((j.input for j in turns if j.input.get(STOPPED_BY)), None)
    if how == "stopped" and by:  # a person's Stop (a declined turn: its reason is the sub)
        out["stopped"] = {"by": user_name(db, by[STOPPED_BY]), "at": by["stopped_at"],
                          "made": made, "total": total,
                          "carry_on": money(again, owner)}  # fmt: skip
    if how == "needs_fix":
        out["failed"] = _failed(db, video, cells, why, owner, again)
    return out


def _take_price(db: Session, video: _Video, c: dict) -> Decimal:
    """What the press that moves a clip on charges: the owner's OK of its held take (with the
    take check riding along, as Approve charges), or a new take as Make a take charges it."""
    from app.clip_takes import take_credits
    from app.routes.jobs import _with_check

    row = next(r for r in video.clips if r.clip_id == c["clip_id"])
    held = next((j for j in video.jobs.get(row.id, []) if j.status == HELD), None)
    if held is not None:
        return _with_check(db, held)
    return take_credits(db, video.project, row)  # with its check, as Make a take quotes it


def _left(video: _Video, cells: list[dict], start: datetime, now: datetime) -> int | None:
    """About how many minutes the clips still to make take (S3-13, "about 2 h 10 min left"):
    at the pace this run has made them, else a typical take's time each."""
    left = sum(c["state"] not in DONE for c in cells)
    made = sum(t.created_at >= start for ts in video.takes.values() for t in ts)
    pace = (now - start).total_seconds() / made if made else video.typical
    return max(1, math.ceil(pace * left / 60)) if left else None


def _blamed(cells: list[dict], why: str) -> dict | None:
    """The failed clip the run stopped on, when its reason names it ("Clip 3's take failed 3
    times"); else None, and the reason itself is shown."""
    named = said(why).lower()
    return next((c for c in cells if c["state"] == "failed"
                 and re.search(rf"\bclip {c['number']}\b", named)), None)  # fmt: skip


def _failed(db: Session, video: _Video, cells: list[dict], why: str, owner: bool,
            again: Decimal) -> dict:  # fmt: skip
    """What stopped the run, and its one-click fixes (rule 22): the clip that failed made
    again at its own price, a clip too long for the model split (S3-11), or carry on from
    where it stopped."""
    carry = {"kind": "carry_on", "label": "Carry on", "price": money(again, owner)}
    bad = _blamed(cells, why)
    long = next((c for c in cells if c["state"] == "too_long"), None)
    if bad is None and long is not None and "makes at most" in why:  # it stopped on that
        return _too_long(db, video, long, owner, carry)
    if bad is None:
        return {"title": "The director stopped", "why": said(why), "clip": None, "fixes": [carry]}
    again = {"kind": "again", "label": "Try again", "price": bad["credits"]}
    return {"title": f"Clip {bad['number']} couldn’t be made", "why": bad["note"],
            "clip": video.pk(bad["clip_id"]), "fixes": [again, carry]}  # fmt: skip


def _too_long(db: Session, video: _Video, c: dict, owner: bool, carry: dict) -> dict:
    """S3-11: a clip longer than its model makes. Split it at its sentence breaks (free; the
    words don't change), with the price of what the new clips then need, or a model that
    makes longer clips (Video settings)."""
    from app import breakdown_fix, plans

    m, n = video.engine, c["number"]
    version = plans.script(db, video.project)
    into = breakdown_fix.split_preview(video.data, version.text if version else "",
                                       c["clip_id"], m.duration.min, m.duration.max)  # fmt: skip
    head = {"title": f"Clip {n} couldn’t be made", "clip": video.pk(c["clip_id"]),
            "why": f"Clip {n} runs {c['seconds']} s, but {m.name} makes at most "
                   f"{m.duration.max} s a clip. Nothing was charged."}  # fmt: skip
    longer = {"kind": "model", "label": "Use a model that makes longer clips…", "price": None}
    if not into:
        return {**head, "fixes": [longer, carry],
                "offer": "One of its sentences is too long to split. Make its shot shorter, or "
                         "use a model that makes longer clips."}  # fmt: skip
    said = next(p for p in video.problems if too_long([p]) == [c["clip_id"]])
    split = {"kind": "split", "label": f"Split it into {len(into)} clips", "price": "free",
             "problem": said, "then": money(_then(db, video.project, into), owner)}  # fmt: skip
    return {**head, "fixes": [split, longer],
            "offer": f"I can split it into {len(into)} clips at the sentence breaks. The words "
                     "don’t change, and the split itself is free."}  # fmt: skip


def _then(db: Session, project: Project, clips: list) -> Decimal:
    """What a split's new clips then need, "up to" (rule 36): a still for each of their
    shots, their prompts written, and a take of each with the watch that rides along."""
    from app import clip_prompts, take_watch
    from app.routes.estimate import _claude, _still, _video

    ws = project.workspace_id
    shots = sum(len(c.shot_ids) for c in clips)
    calls = len(clip_prompts.batches(Breakdown(hook="", scenes=[], clips=clips),
                                     [c.id for c in clips]))  # fmt: skip
    return (_still(db, ws, project) * shots + _claude(db, ws) * calls
            + _video(db, ws, sum(c.seconds for c in clips), project)
            + take_watch.per_take(db, ws) * len(clips))  # fmt: skip


def thread_items(db: Session, project: Project, viewer: User | None) -> list[dict]:
    """The director's part of the chat: one item a run (its progress card in a line, `run`
    naming the record) and each delivery's note; its cards are app/asks'."""
    from app import delivery

    out, every, owner = [], runs(db, project), bool(viewer and viewer.is_owner)
    for run_id, turns in every.items():
        how, why = ending(turns)
        head = {} if how else record(db, project, viewer) or {}  # the newest run, as they see it
        if how:
            text = (_took(turns) if how == "delivered" else "Stopped" if why == "Stopped."
                    else said(why))  # fmt: skip
        else:  # its card in a line
            text = " · ".join(x for x in (head.get("title"), head.get("sub")) if x)
        status = "done" if how else "held" if head.get("status") == "waiting" else "running"
        out.append({"id": f"r{turns[0].id}", "kind": "move", "at": turns[0].created_at.isoformat(),
                    "who": "Director", "text": text, "status": status, "run": run_id})  # fmt: skip
        for j in turns:  # the owner's OK at its own limit is its card's answer (app/asks)
            if j.input.get("result") == "Delivered.":
                note = delivery.shown((j.output or {}).get("note"), owner)
                out.append({"id": f"t{j.id}", "kind": "move", "at": j.created_at.isoformat(),
                            "who": "Director", "status": "done", "note": note,
                            "text": delivery.plain(note) if note
                            else said(j.input["ended"])})  # fmt: skip
    return out


def seen(db: Session, user: User, project: Project, take_ids: list[int]) -> None:
    """This person watched these takes of the video: their clips stop being outlined."""
    mine = set(db.scalars(select(ClipTake.id).join(ProjectClip, ProjectClip.id == ClipTake.clip_id)
                          .where(ProjectClip.project_id == project.id,
                                 ClipTake.id.in_(take_ids))))  # fmt: skip
    had = set(db.scalars(select(TakeSeen.take_id).where(TakeSeen.user_id == user.id,
                                                       TakeSeen.take_id.in_(mine))))  # fmt: skip
    from sqlalchemy.exc import IntegrityError

    db.add_all(TakeSeen(take_id=t, user_id=user.id) for t in sorted(mine - had))
    try:
        db.commit()
    except IntegrityError:  # the same mark from another press at the same moment: it's there
        db.rollback()
