"""The presenter's host (a format whose guide says `host: yes`: Presenter). Once the narration
is made, the host says it on camera: one still of the cast host's look, waist-up on flat
chroma green (the video's picture model, as a storyboard still is drawn), then one HeyGen
Avatar IV take of the whole narration from that still, lip-synced to it (Reed, 4 Nov: the
corner presenter is HeyGen, not P-Video; app/talker.py has HeyGen's settings). Each is a priced
job like a take; a failed one is tried again once on its own, then Make again makes it (rule
22). The cut keys the take over the narrated B-roll (host_layer.lay_over), bottom right unless
a shot's action is on the right (`sides`; the cut editor's presenter spans after). In the UGC
style the host is a talker instead: the still is in their own room and the talker's shots are
cut from the take (app/talker.py)."""

import hashlib
import math
import re
import subprocess
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import guides, narration, take_watch, talker, watch_report
from app.credits import estimate
from app.models.accounts import User
from app.models.clips import HostPiece, ProjectClip
from app.models.files import StoredFile
from app.models.jobs import WAITING, Job, JobStatus
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.songs import SongTake

STILL, PIECE = "host_still", "host_piece"
NOT_PRESENTER = "This video has no host: its format isn't Presenter."
NO_NARRATION = "Make the narration first: the host says it."
MAKING = "The host is being made. It's ready in a moment."
MADE = ("The host is made. To change it, draw its still again with a note: its take is made "
        "again from it.")  # fmt: skip
NOT_READY = "Make the host first: a presenter video lays its host over the B-roll."
NO_PIECE = "There's no such piece of the host."
STILL_PROMPT = (
    "{who}, for a green-screen composite: waist-up, centred, facing the camera at eye level and "
    "looking into the lens, both arms and the waist in frame with green on both sides, a little "
    "space above the head, lips slightly parted as if about to speak. Soft, even frontal light. "
    "The background is one perfectly flat, evenly lit, solid chroma-key green, hex #00B140, the "
    "same single colour from edge to edge with no gradient, texture, floor or shadow, and clean "
    "crisp edges around the hair, ears and shoulders."
)  # the paid test's host still, waist-up as its report advises
GREEN = (
    "They stay in place, waist-up. The background stays one flat, solid chroma-key green "
    "with no shadows or objects. Locked-off static camera."
)  # every take on green: it's keyed
TALK = (
    "The host talks straight into the camera: the mouth moves with the stressed words, the "
    "eyebrows move, they blink, and their hands come up at chest height in open-palm and "
    "pointing gestures."
)  # HeyGen's motion prompt for the host on green when the director writes none
RIGHT = re.compile(r"\b(?:on|to|at) the right\b|\bright(?:-hand)? (?:side|corner|edge)\b|"
                   r"\b(?:frame|bottom|lower)[- ]right\b", re.I)  # fmt: skip
LEFT = re.compile(RIGHT.pattern.replace("right", "left"), re.I)


def hosted(script) -> bool:
    """The script's format has a host (its guide's `host: yes`)."""
    from app.script_library import format_id

    return bool(script) and any(f["id"] == format_id(script) and f.get("host")
                                for f in guides.formats())  # fmt: skip


# How the presenter appears (Reed's L3, 4 Nov: a saved presenter is a face and a voice; how
# they appear is chosen per video): in one spot the whole time, talking to camera in their own
# room with B-roll cut in or in a corner keyed over the B-roll (both one HeyGen take of our own
# voice track), or moving around in the story (their shots made like the B-roll, on the style's
# own model: Omni 1.2 in UGC, Reed 6 Nov)
HOW = ("talks", "corner", "acts")
ACTS = ("The presenter acts in the story: their shots are made like the B-roll, with no take of "
        "their own to make.")  # fmt: skip


def how(project: Project) -> str:
    """The video's own choice, else its style's start: a UGC talker talks, the rest sit in a
    corner."""
    from app import looks

    if project.presenter in HOW:
        return project.presenter
    return "talks" if looks.base(project.look or looks.DEFAULT) in talker.LOOKS else "corner"


def presents(db: Session, project: Project) -> bool:
    """A Presenter video, however its presenter appears."""
    return hosted(narration.video_script(db, project))


def on(db: Session, project: Project) -> bool:
    """A Presenter video whose presenter is one HeyGen take (talks or in a corner); one who
    acts in the story has no take: their shots are made like the B-roll (app/model_map)."""
    return presents(db, project) and how(project) != "acts"


def _narration(db: Session, project: Project) -> SongTake | None:
    """The narration the video uses, once it's made and timed."""
    take = db.get(SongTake, project.song_take_id) if project.song_take_id else None
    ok = take and take.kind == narration.KIND and take.file_id and take.timing and take.seconds
    return take if ok else None


def rows(db: Session, project: Project) -> list[HostPiece]:
    """The host of the narration in use: the still (0), then each piece in order."""
    return list(db.scalars(select(HostPiece).where(
        HostPiece.project_id == project.id, HostPiece.take_id == (project.song_take_id or 0),
        HostPiece.how == how(project))
        .order_by(HostPiece.number)))  # fmt: skip


def _jobs(db: Session, project: Project) -> dict[int, Job]:
    """Each row's newest job."""
    step = Job.input["step"].as_string()
    jobs = db.scalars(select(Job).where(Job.project_id == project.id, step.in_((STILL, PIECE)))
                      .order_by(Job.id))  # fmt: skip
    return {j.input["host_piece_id"]: j for j in jobs}


def _state(row: HostPiece, job: Job | None) -> str:
    if job and job.status in WAITING:
        return "making"
    if row.file_id:
        return "ready"
    return "failed" if job and job.status in (JobStatus.failed, JobStatus.cancelled) else "none"


def _length(start: float, end: float) -> int:
    return max(1, math.ceil(end - start - 0.01))  # priced in whole seconds, up to


def _seconds(row: HostPiece) -> int:
    return _length(row.start, row.end)


def _piece_price(db: Session, ws: int, seconds: int) -> Decimal:
    """The host's one HeyGen take, at 720p, and the director's watch of it (rule 11)."""
    shape = {"model": talker.MODEL, "input": {"resolution": talker.RESOLUTION}}
    return estimate(db, ws, "video", Decimal(seconds), shape) + take_watch.per_take(db, ws)


def _still_price(db: Session, project: Project) -> Decimal:
    """The still; a talker's with its check before any take, and drawn once more if the check
    finds it wrong (`host_watch.check_still`)."""
    from app.storyboard import image_model, still_credits

    one = still_credits(db, project.workspace_id, image_model(project))
    if not talker.on(db, project):
        return one
    from app import item_checks

    return 2 * (one + item_checks.price(db, project, "frame"))


def price(db: Session, project: Project, number: int | None = None) -> Decimal:
    """Make the host (`number` None: every row not made yet) or Make again one row; a new
    still makes every piece again from it."""
    have, ws = rows(db, project), project.workspace_id
    if not have:  # none planned yet: the still and the take of the narration in use
        take = _narration(db, project)
        try:
            spans = _spans(take) if take else []
        except ValueError:  # past HeyGen's 10 minutes: Make the host says so
            spans = []
        return (_still_price(db, project) if spans else Decimal(0)) + sum(
            (_piece_price(db, ws, _length(a, b)) for a, b in spans), Decimal(0)
        )
    todo = [r for r in have if not r.file_id] if number is None else [
        r for r in have if r.number == number]  # fmt: skip
    if any(r.number == 0 for r in todo):
        todo = have
    return sum((_still_price(db, project) if r.number == 0 else
                _piece_price(db, ws, _seconds(r)) for r in todo), Decimal(0))  # fmt: skip


def run_price(db: Session, draft: ScriptDraft, seconds: int, video=None,
              redos: int = 0) -> Decimal:  # fmt: skip
    """A director run's "up to" for the host (rule 36): the still and every second of the
    narration in one HeyGen take, rounded up a second. A presenter who acts in the story has
    no take: their shots are made on the video's model like the B-roll (Omni 1.2 in UGC, Reed,
    6 Nov), already in the takes' price. With `redos`, each made that many times again by its
    watch (app/host_watch), as a run may."""
    from app.models.script_library import Script
    from app.storyboard import image_model, still_credits

    script = db.get(Script, draft.script_id)
    if not hosted(script) or (video is not None and how(video) == "acts"):
        return Decimal(0)
    still = _still_price(db, video) if video is not None else still_credits(
        db, script.workspace_id, image_model(video))  # fmt: skip
    return still + _piece_price(db, script.workspace_id, seconds + 1) * (1 + redos)


def state(db: Session, project: Project) -> dict:
    """{state: none | making | ready | failed, pieces: [...], credits}: what the director reads
    and the clips page shows (number 0 is the still)."""
    have, jobs = rows(db, project), _jobs(db, project)
    lost = {i: j.error for i, j in jobs.items() if j.status == JobStatus.failed}
    pieces = [{"number": r.number, "start": r.start, "end": r.end, "file_id": r.file_id,
               "earlier": r.earlier or [], "state": _state(r, jobs.get(r.id)),
               "error": lost.get(r.id, ""), "credits": float(price(db, project, r.number)),
               "watch": watch_report.shown(db, r, "piece") if r.number else None}
              for r in have]  # fmt: skip
    states = {p["state"] for p in pieces}
    whole = ("none" if not pieces else "making" if "making" in states else "ready"
             if states == {"ready"} else "failed" if "failed" in states else "none")  # fmt: skip
    talks = {"talker": talker.share(db, project)} if talker.on(db, project) else {}
    return {"state": whole, "pieces": pieces, "credits": float(price(db, project)), **talks}


def _spans(take: SongTake) -> list[tuple[float, float]]:
    """The host's one piece: the whole narration (HeyGen: one continuous take)."""
    return talker.whole(float(take.seconds))


def _store(db: Session, storage, project: Project, data: bytes, name: str) -> StoredFile:
    key = f"{project.workspace_id}/{uuid.uuid4().hex}"
    storage.put(key, data)
    stored = StoredFile(workspace_id=project.workspace_id, key=key, filename=name,
                        content_type="audio/mpeg", size=len(data),
                        sha256=hashlib.sha256(data).hexdigest())  # fmt: skip
    db.add(stored)
    db.flush()
    return stored


def _cut(sound: bytes, start: float, end: float) -> bytes:
    """A piece of the narration, as an MP3 (free: ffmpeg)."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in").write_bytes(sound)
        command = ["ffmpeg", "-v", "error", "-y", "-i", "in", "-ss", f"{start:.2f}", "-to",
                   f"{end:.2f}", "-c:a", "libmp3lame", "out.mp3"]  # fmt: skip
        done = subprocess.run(command, cwd=folder, capture_output=True, timeout=120)  # noqa: S603
        if done.returncode:
            raise HTTPException(422, "The narration's file can't be read. Make it again.")
        return (folder / "out.mp3").read_bytes()


def _plan(db: Session, storage, project: Project, take: SongTake) -> list[HostPiece]:
    """The still's row and each piece's, with its piece of the narration stored (free)."""
    sound = storage.get(db.get(StoredFile, take.file_id).key)
    try:
        spans = _spans(take)
    except ValueError as too_long:
        raise HTTPException(409, str(too_long)) from too_long
    made = [HostPiece(project_id=project.id, take_id=take.id, number=0, how=how(project))]
    for n, (a, b) in enumerate(spans, 1):
        audio = _store(db, storage, project, _cut(sound, a, b), f"host piece {n}.mp3")
        made.append(HostPiece(project_id=project.id, take_id=take.id, number=n, start=a, end=b,
                              audio_file_id=audio.id, how=how(project)))  # fmt: skip
    db.add_all(made)
    db.flush()
    return made


def host_look(db: Session, project: Project):
    """The cast look that says the narration: the one whose role the script's first speaker
    label names, else the video's first cast look; None with no cast."""
    from app.cast_roles import cast_roles, labels
    from app.prompts.check import LABEL
    from app.storyboard import cast_looks

    looks = cast_looks(db, project)
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    said = [m[1] for x in (draft.text if draft else "").splitlines() if (m := LABEL.match(x))]
    roles = cast_roles(db, project)
    for item in looks if said else []:
        if any(labels(said[0], s.role) for s in roles.get(item.id, [])):
            return item
    return looks[0] if looks else None


def still_input(db: Session, project: Project, row: HostPiece, note: str = "") -> dict:
    """The host's still: the cast host's sheet in the video's look, else the look's own words;
    on green, or a UGC talker where the plan puts them (talker.STILL_PROMPT). `note`: what a
    redraw changes."""
    from app.sheets import sheet_for
    from app.storyboard import image_model
    from app.storyboard import still_input as drawn

    item = host_look(db, project)
    sheet = sheet_for(db, project, item)[:1] if item else []
    look = guides.tokens(project.look or "house")["sheet_look"]
    who = (f"The host, {item.name}, exactly as [Image1], their character sheet: the same face, "
           "hair, build and outfit" if sheet else
           f"The host, drawn in this look: {look}")  # fmt: skip
    talks = talker.on(db, project)
    place = talker.frame(db, project) if talks else None  # what HeyGen gets: their clip's place
    shown = f"[Image{len(sheet) + 1}] (the opening still of their clip)"
    where = (f"exactly where {shown} shows them, its place and light, alone" if place
             else talker.where(db, project))  # fmt: skip
    said = (talker.STILL_PROMPT if talks else STILL_PROMPT).format(who=who, where=where)
    said += f" Change from the last still: {note.strip()[:500]}" if note.strip() else ""
    pictures = [*sheet, *([place] if place else [])]
    job = drawn(image_model(project), said, project.aspect_ratio, pictures)
    return {**job, "step": STILL, "project_id": project.id, "host_piece_id": row.id,
            "made_with": {"cast": _cast(db, project)}}  # fmt: skip


def _cast(db: Session, project: Project, check: bool = False) -> dict[str, str]:
    """The host as the cast and places OK knows them; `check`: refused while they wait for it
    (every piece shows them, a still or one piece made again)."""
    from app import cast_gate
    from app.storyboard import assets

    item, known = host_look(db, project), assets(db, project)
    who = [f"char:{item.id}"] if item else []
    if check:
        cast_gate.require(db, project, who, known)
    return cast_gate.stamp(db, project, who, known)


def _piece(db: Session, user: User, project: Project, row: HostPiece, still: int,
           motion: str = "", note: str = "", mark: dict | None = None,
           **kwargs) -> Job:  # fmt: skip
    """Queue the host's HeyGen take, with the director's `motion` note (on green: TALK when
    it gives none); `note`: the fix its watch asks for (app/host_watch); `mark`: more input."""
    from app.routes.jobs import enqueue

    talks = talker.on(db, project)
    motion = motion or (talker.MOTION if talks else TALK)
    if note:  # first, so the fit to HeyGen's limit never cuts it
        motion = f"{note[:200].rstrip('.')}. {motion}"
    if talks:  # nobody else in it, whatever the note says (video 281: strangers, three times)
        room = talker.LONGEST_MOTION - len(talker.ALONE) - 1
        data = talker.piece_input(project, row, still, f"{motion[:room]} {talker.ALONE}")
    else:  # on green, whatever the director's note says: the cut keys it
        room = talker.LONGEST_MOTION - len(GREEN) - 1
        said = " ".join(motion.split())[:room]
        data = talker.piece_input(project, row, still, f"{said} {GREEN}")
    data = {**data, "made_with": {**(data.get("made_with") or {}), "cast": _cast(db, project)}}
    return enqueue(db, user, "video", {**data, **(mark or {})}, units=_seconds(row),
                   project=project, provider=talker.PROVIDER, **kwargs)  # fmt: skip


def make(db: Session, user: User, project: Project, storage, number: int | None = None,
         motion: str = "") -> str:  # fmt: skip
    """Make the host (`number` None: every row not made yet), or Make again one row. A still
    is drawn first and its pieces follow it (priced together: the press holds them). `motion`:
    a talker's motion note from the director; a remake with none keeps the last one."""
    from app.routes.jobs import enqueue

    if not on(db, project):
        raise HTTPException(409, ACTS if presents(db, project) else NOT_PRESENTER)
    take = _narration(db, project)
    if take is None:
        raise HTTPException(409, NO_NARRATION)
    if talker.on(db, project) and not talker.clips(db, project):  # never seen: nothing spent
        raise HTTPException(409, talker.NO_SHOTS)
    _cast(db, project, check=True)
    have = rows(db, project) or _plan(db, storage, project, take)
    jobs = _jobs(db, project)
    if any(_state(r, jobs.get(r.id)) == "making" for r in have):
        raise HTTPException(409, MAKING)
    todo = [r for r in have if not r.file_id] if number is None else [
        r for r in have if r.number == number]  # fmt: skip
    if number is not None and not todo:
        raise HTTPException(404, NO_PIECE)
    if not todo:
        raise HTTPException(409, MADE)
    still = have[0]
    motion = motion or _motion(jobs, have)
    if still in todo:  # every piece follows a new still, prepaid (`saved`)
        hold = sum((_piece_price(db, project.workspace_id, _seconds(r)) for r in have[1:]),
                   Decimal(0))  # fmt: skip
        drawn = {**still_input(db, project, still), **({"motion": motion} if motion else {})}
        enqueue(db, user, "image", drawn, project=project, provider="replicate",
                hold=hold)  # fmt: skip
        return "Drawing the host, then making its take."
    for row in todo:
        _piece(db, user, project, row, still.file_id, motion)
    return "Making the host's take." if len(todo) == 1 else f"Making the host's {len(todo)} takes."


def redraw(db: Session, user: User, project: Project, note: str, mark: dict | None = None,
           **kwargs) -> str:  # fmt: skip
    """The host's still drawn again with `note` (video 281: three HeyGen tries from one still
    in the wrong room, and no way to draw it again), then its take made again from it, priced
    together like Make the host; `mark` goes on to the take (a watch's remake)."""
    from app.routes.jobs import enqueue

    have = rows(db, project)
    if not have or not have[0].file_id:
        return make(db, user, project, None)
    jobs = _jobs(db, project)
    if any(_state(r, jobs.get(r.id)) == "making" for r in have):
        raise HTTPException(409, MAKING)
    _cast(db, project, check=True)
    hold = sum((_piece_price(db, project.workspace_id, _seconds(r)) for r in have[1:]),
               Decimal(0))  # fmt: skip
    motion = _motion(jobs, have)
    drawn = {**still_input(db, project, have[0], note), **({"motion": motion} if motion else {}),
             **({"mark": mark} if mark else {})}  # fmt: skip
    enqueue(db, user, "image", drawn, project=project, provider="replicate", hold=hold,
            **kwargs)  # fmt: skip
    return f"Drawing the host's still again ({note.strip()}), then making its take from it."


def _motion(jobs: dict[int, Job], have: list[HostPiece]) -> str:
    """The motion note the host's take was last made with ("" when none was written)."""
    made = [jobs[r.id] for r in have if r.id in jobs]
    said = [j.input.get("motion") or (j.input.get("input") or {}).get("motion_prompt")
            for j in made]  # fmt: skip
    said = [(m or "").removesuffix(f" {GREEN}").removesuffix(f" {talker.ALONE}")
            for m in said]  # the director's own words  # fmt: skip
    return next((m for m in said if m and m not in (talker.MOTION, TALK)), "")


def _keep(row: HostPiece, job: Job) -> bool:
    file_ids = (job.output or {}).get("file_ids") or []
    if not file_ids:
        return False
    if row.file_id and row.file_id != file_ids[0]:  # the one before stays, to see
        row.earlier = [*(row.earlier or []), row.file_id]
    row.file_id = file_ids[0]
    return True


def saved(db: Session, job: Job) -> None:
    """A still or a piece is made. A still makes every piece again from it (prepaid)."""
    row = db.get(HostPiece, job.input["host_piece_id"])
    project = db.get(Project, job.project_id)
    if row is None or row.take_id != project.song_take_id or not _keep(row, job):
        return  # a narration since: this host is for the old one
    from app import host_watch

    if job.input["step"] != STILL:  # rule 11: looked at as it lands
        return host_watch.queue_safely(db, job, row)
    if talker.on(db, project) and host_watch.check_still(db, job, row):
        return  # its take waits for the still's check (`pieces` after it)
    pieces(db, job, row)


def pieces(db: Session, job: Job, row: HostPiece) -> None:
    """Every piece made again from the still `job` drew (prepaid: its press held them)."""
    project, user = db.get(Project, job.project_id), db.get(User, job.created_by_id)
    for piece in rows(db, project)[1:]:
        _piece(db, user, project, piece, row.file_id, job.input.get("motion", ""),
               mark=job.input.get("mark"), prepaid=True)  # fmt: skip


def labels(db: Session, project: Project) -> list[str]:
    """What the final cut lays over its takes from the host (so a new piece shows as changes)."""
    if not on(db, project):
        return []
    return [f"host:{r.number}/{r.file_id}" for r in rows(db, project)[1:] if r.file_id]


def sides(db: Session, project: Project) -> list[tuple[float, str]]:
    """Where the host stands over time: bottom right, or left while a clip's action is on the
    right (the spec: "switching sides so he never covers the action")."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    shots = {s["id"]: s for sc in (bd.data if bd else {}).get("scenes", []) for s in sc["shots"]}
    out: list[tuple[float, str]] = []
    clips = sorted(db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)),
                   key=lambda c: (c.song_slice or {}).get("start", 0))  # fmt: skip
    ids = {c["id"]: c["shot_ids"] for c in (bd.data if bd else {}).get("clips", [])}
    for clip in clips:
        said = " ".join(shots.get(i, {}).get("action", "") for i in ids.get(clip.clip_id, []))
        at = round((clip.song_slice or {}).get("start", 0), 2) if out else 0.0
        if not out or out[-1][1] != side(said):
            out.append((at, side(said)))
    return out or [(0.0, "right")]


def side(action: str) -> str:
    """The host's side under a shot: left when its action is on the right, else right."""
    return "left" if RIGHT.search(action) and not LEFT.search(action) else "right"


def ready(db: Session, project: Project) -> bool:
    pieces = rows(db, project)[1:]
    return bool(pieces) and all(r.file_id for r in pieces)
