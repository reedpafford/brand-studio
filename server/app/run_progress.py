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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import asks, model_map
from app.models.accounts import User
from app.models.brands import Brand
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import WAITING, Job, JobStatus, Usage
from app.models.projects import Project
from app.models.seen import TakeSeen
from app.models.storyboards import StoryboardFrame

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
        self.clips = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)
                                .order_by(ProjectClip.id)).all()  # fmt: skip
        ids = [c.id for c in self.clips]
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
        self.model = video_model(project).name
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
    slots = video_slots(db, project)
    roles = [s.role for s in slots]
    cast = _and(roles)
    face = host.host_look(db, project) if host.presents(db, project) else None
    if line := _cast(db, project, slots, face):
        words["cast"] = line
    if director_song.kind(db, project):
        audio = director_song.state(db, project) or {"takes": []}
        used = next((t for t in audio["takes"] if t["used"]), None) or {}
        long = f": {used['seconds']:.1f} s" if used.get("seconds") else ""
        right = used.get("timed") and not used.get("missing") and not used.get("misheard")
        words["voice"] = (f"Song{long}" + (", every lyric heard" if right else "")
                          if "style" in audio else f"Voice track{long}"
                          + (", words checked against the script" if right else ""))  # fmt: skip
    redrawn = (turns[-1].input.get(RUN) or {}).get("redraws", {})
    why = _redrawn(db, project, turns[0], set(redrawn))  # S3-04: "2 redrawn (the label faced away)"
    words["stills"] = (
        (f"Stills: {video.drawn} drawn" if video.drawn else "Stills")
        + (f", {sum(redrawn.values())} redrawn" if redrawn else "")
        + (f" ({why})" if why else "")
    )
    hosted = host.on(db, project)
    models, reasons = _models(db, video, cells)
    on = ", ".join(f"{name} ({n})" if len(models) > 1 else name for name, n in models.items())
    words["prompts"] = ("Clip prompts written · " + (f"B-roll on {on}, presenter on HeyGen"
                        if hosted else f"on {on}")) if total else "Clip prompts"  # fmt: skip
    if hosted:
        reasons.append("HeyGen lip-syncs the presenter to the voice")
    words["takes"] = f"Making takes: {made} of {total}" if made < total else f"Takes: {total} made"
    if watching := _watching(db, video, cells, owner):
        words["watching"] = watching[0]
    if hosted:
        from app.models.songs import SongTake

        take = db.get(SongTake, project.song_take_id) if project.song_take_id else None
        music = ", music under the voice" if take and take.music_file_id else ""  # its own bed
        who = face.name if face is not None else cast or "the presenter"
        words["host"] = f"Lay {who} over the B-roll{music}"
    words["cut"] = "Watch and listen to the whole cut, then deliver"
    first = next((c for c in cells if c["state"] == "making"), None)
    subs = {"stills": f"{video.drawn} of {video.stills} drawn" if video.stills else "",
            "takes": f"Clip {first['number']} · scene {first['scene']} · {first['seconds']} s · "
                     f"about {first['minutes_left']} min" if first else "",
            "watching": watching[1] if watching else "",
            "prompts": "; ".join(reasons)}  # fmt: skip
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
        shown = state in ("now", "wait") or key == "prompts" and state == "done"  # why each model
        out.append({"key": key, "state": state, "text": words[key],
                    "sub": subs.get(key, "") if shown else ""})  # fmt: skip
    return out


def _and(names: list[str]) -> str:
    return ", ".join(names[:-1]) + f" and {names[-1]}" if len(names) > 1 else "".join(names)


def _cast(db: Session, project: Project, slots: list, face) -> str:
    """S3-04's cast line: who's in it, the voice it's read in, and whether they're the brand's
    saved ones ("Cast: Dr. Pickle and the cloned voice, both saved in Resilia") or all made
    for this video. A role not cast yet isn't named; a look kept by a script isn't saved."""
    from app import director_song, voices
    from app.cast_roles import pick
    from app.models.library import LibraryItem

    brand = db.get(Brand, project.brand_id)
    items = [(s.role, db.get(LibraryItem, pick(db, project, s) or 0)) for s in slots]
    items = [(name, i) for name, i in items if i is not None]  # cast; an archived look isn't
    if face is not None and all(i.id != face.id for _, i in items):
        items.insert(0, (face.name, face))  # the presenter, when no role is them
    names = [name for name, _ in items]
    saved = [i.owner_project_id is None and i.owner_script_id is None and brand in i.brands
             for _, i in items]  # fmt: skip
    here = [i.owner_project_id == project.id for _, i in items]
    read = ""  # an app voice: not the brand's to save, so said apart
    if face is not None or director_song.kind(db, project) == "narrated":
        from app.models.songs import SongTake

        take = db.get(SongTake, project.song_take_id) if project.song_take_id else None
        # the voice its narration was read in; before one, the one it will be (director_song)
        ref = ((take.voice if take is not None else "") or voices.picked(db, project)
               or asks.voice(db, project) or director_song._voice(db, project))  # fmt: skip
        voice = voices.named(db, project.workspace_id, ref, project.brand_id)
        if voice is not None:  # the brand's own, or its style's, listed with them (S8-04, L4)
            names.append(f"the {voice.kind} voice")  # "the cloned voice"
            saved.append(True)
        elif ref in voices.stock_keys():
            read = f"the {voices.stock(ref)['name']} voice"
    if not names:
        return f"Cast: read in {read}" if read else ""
    both = "" if len(saved) == 1 else "both " if len(saved) == 2 else "all "
    end = (f", {both}saved in {brand.name}" if all(saved)
           else ", made for this video" if here and all(here) and len(here) == len(saved)
           else "")  # fmt: skip
    return f"Cast: {_and(names)}{end}" + (f"; read in {read}" if read else "")


LOWER = ("The", "A", "An", "It", "Its", "This", "That", "His", "Her", "Their", "One", "Some")
SHOT = re.compile(r"^(?:shot\s+)?(\d+)\.\d+\b:?\s*", re.I)  # a finding's "3.1 shows him ..."


def _redrawn(db: Session, project: Project, first: Job, shots: set[str]) -> str:
    """Why the run's stills were redrawn, from its review's worst finding, as one short reason
    in plain words (rule 23): "the capsule label faced away"; a finding in the review's own
    shape ("4.2 shows him sitting; the beat is the jar exploding") names the clip that shot is
    in ("clip 14's still shows him sitting"), never a bare shot number."""
    from app import clip_prompts, still_review

    if not shots:
        return ""
    rows = db.scalars(select(Job).where(Job.project_id == project.id, Job.id >= first.id,
                                        Job.input["step"].as_string() == still_review.STEP,
                                        Job.status == JobStatus.succeeded))  # fmt: skip
    every = [f for j in rows for f in (j.output or {}).get("findings") or []]
    f = next((f for f in every if f.get("shot_id") in shots
              and said(f.get("problem", "")).strip(" .")), None)  # fmt: skip
    if f is None:
        return ""
    p = said(f["problem"])
    if m := SHOT.match(p):
        bd = clip_prompts.newest(db, project)
        clip = next((c["id"] for c in (bd.data if bd else {}).get("clips", [])
                     if f["shot_id"] in c.get("shot_ids", [])), "")  # fmt: skip
        whose = f"clip {clip.removeprefix('c')}'s" if clip else "the"
        p = f"{whose} still {p[m.end() :]}"
    p = p.split("; ", 1)[0].strip().rstrip(".")
    word = p.split(" ", 1)[0]
    return p[0].lower() + p[1:] if word in LOWER else p  # never a name ("Dr. Pickle's")


TRIES = 4  # clips read a model for its reason, at most


def _models(db: Session, video: _Video, cells: list[dict]) -> tuple[dict[str, int], list[str]]:
    """The clips' models with how many each ({"Seedance 2.0": 20, "Seedance 1 Lite": 4}),
    and why each, as the Clips tab says it ("Seedance 2.0: Dr. Pickle's default"): one read a
    model, whatever the video's length."""
    counts: dict[str, int] = {}
    for c in cells:
        counts[c["model"]] = counts.get(c["model"], 0) + 1
    rows = {r.clip_id: r for r in video.clips if getattr(r, "id", None) is not None}
    reasons = []
    for name in counts:
        tried = [rows[c["clip_id"]] for c in cells if c["model"] == name and c["clip_id"] in rows]
        for row in tried[:TRIES]:  # a talker's clip can sit under the B-roll's model: next one
            told = model_map.why(db, video.project, row)
            if told["name"] == name and told["why"]:
                reasons.append(f"{name}: {told['why'].rstrip('.')}")
                break
    return counts or {video.model: 0}, reasons


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


def spent(db: Session, project: Project, since: datetime,
          until: datetime | None = None) -> tuple[Decimal, Decimal]:  # fmt: skip
    """(credits charged, real dollars) on the video from `since` to `until`: a run's spend."""
    from app.credits import COUNTED

    mine = (Job.project_id == project.id, Job.created_at >= since,
            *((Job.created_at <= until,) if until else ()))  # fmt: skip
    credits = db.scalar(select(func.coalesce(func.sum(Job.credits), 0)).where(
        *mine, Job.status.in_(COUNTED)))  # fmt: skip
    usd = db.scalar(select(func.coalesce(func.sum(Usage.cost_usd), 0)).join(
        Job, Job.id == Usage.job_id).where(*mine))  # fmt: skip
    return Decimal(credits), Decimal(usd)


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
    charged, usd = spent(db, project, start)
    up_to = price_of(db, project)
    if how == "delivered":
        head = ("delivered", _took(turns), _n(total, "clip") + (
            f" · {redone} redone after watching" if redone else ""), "done")  # fmt: skip
    elif how:
        bad = _blamed(cells, why) if how == "needs_fix" else None
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
           "spent_usd": float(usd) if owner else None,
           "changed": [{k: c[k] for k in ("clip_id", "number", "take_id", "frame_file_id",
                                          "watched")} for c in cells if c["changed"]],
           "stopped": None, "failed": None}  # fmt: skip
    by = next((j.input for j in turns if j.input.get(STOPPED_BY)), None)
    if how == "stopped" and by:  # a person's Stop (a declined turn: its reason is the sub)
        out["stopped"] = {"by": user_name(db, by[STOPPED_BY]), "at": by["stopped_at"],
                          "made": made, "total": total,
                          "carry_on": money(again, owner)}  # fmt: skip
    if how == "needs_fix":
        out["failed"] = _failed(video, cells, why, owner, again)
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


def _failed(video: _Video, cells: list[dict], why: str, owner: bool, again: Decimal) -> dict:
    """What stopped the run, and its one-click fixes (rule 22): the clip that failed made
    again at its own price, or carry on from where it stopped."""
    carry = {"kind": "carry_on", "label": "Carry on", "price": money(again, owner)}
    bad = _blamed(cells, why)
    if bad is None:
        return {"title": "The director stopped", "why": said(why), "clip": None, "fixes": [carry]}
    again = {"kind": "again", "label": "Try again", "price": bad["credits"]}
    return {"title": f"Clip {bad['number']} couldn’t be made", "why": bad["note"],
            "clip": video.pk(bad["clip_id"]), "fixes": [again, carry]}  # fmt: skip


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
                note = delivery.shown(db, project, (j.output or {}).get("note"), owner)
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
