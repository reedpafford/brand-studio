"""The UGC talker (Reed, 3 Nov: "Heygen for still imaged UGC talking, yes."). In a Presenter
video in the UGC style the host isn't keyed into a corner: one still of the talker in their own
room, then ONE HeyGen Avatar IV take of the whole narration (the MiniMax voice with its room
sound, app/room.py), lip-synced from that still (app/host.py makes both, priced like takes). The
plan's talker shots (in a narration, `sung`: the talker says that stretch to the lens) are cut
from that take at the final cut; every other shot is B-roll cut in over the voice, so the cut
alternates talker and B-roll. Settings from HeyGen's docs and the paid tests (batch-b,
.context/team/research/ugc-realism.md; th-20s, .context/tests/th-20s/REPORT.md): type image,
720p, expressiveness high (th-20s: high with a motion prompt for the moment clearly beat medium
with a fixed one), and a motion prompt the director writes for this narration's emotion and
lines (`motion`); the fixed line's "one easy hand gesture" made a stray hand pop in behind a
steering wheel, so the fallback names no hands."""

import hashlib
import subprocess
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import narration
from app.models.clips import ClipTake, ProjectClip
from app.models.files import StoredFile
from app.models.projects import Project

LOOKS = ("ugc",)  # styles whose host talks in their own room, not keyed in a corner
MODEL, RESOLUTION, PROVIDER = "heygen-avatar-iv", "720p", "heygen"
VOICE = narration.MINIMAX_VOICES[0]  # a talker's voice when the director names none
LONGEST = 600.0  # HeyGen: an avatar's audio input runs 10 minutes at most
FIT = 1920  # HeyGen takes images under 2K: "as much resolution as you have"
STILL_PROMPT = (
    "{who}, filmed by themselves on their phone: chest-up, centred, facing the camera at eye "
    "level and looking straight into the lens, the whole head and both shoulders in frame with "
    "a little space above the head, a relaxed, natural expression, the mouth closed or just "
    "parted. Nothing covers the face: no sunglasses, no hat brim, no hand near the mouth. They "
    "are {where}, in focus behind them, lit by soft daylight from the front. A real vertical "
    "phone photo, unretouched: natural skin with pores, no studio light, no shallow-focus blur, "
    "only this one person in it, alone in the frame."
)  # HeyGen: a clear, front-facing, evenly lit portrait, the whole head in frame, one person
ROOM = "in their own real, lived-in room that says who they are"  # with no plan to say where
EXPRESSIVENESS = "high"  # HeyGen: high, medium or low ("energy and range of movement")
MOTION = (
    "They stay where they are and talk straight into the phone lens like a real selfie video: "
    "small natural head nods and tilts, blinks, eyebrows and mouth that move with the feeling "
    "of the words. The camera stays locked off the whole time."
)  # when the director writes none (Make the host pressed by a person)
ALONE = ("They are alone in the frame the whole time; the place behind them stays exactly as "
         "the picture shows it, still and empty.")  # fmt: skip  # every talker take: said as what
# is there, never as what isn't (#1392's HeyGen notes: a negative can suggest it; 281's strangers)
LONGEST_MOTION = 600  # characters: a motion note is a few sentences
SAID = ("The talker says this clip: its picture is cut from the talker's take. To change how "
        "the talker looks or where they are, press Make it again on the presenter in the "
        "Cast tab: their still is drawn again and their take made from it.")  # fmt: skip
NO_SHOTS = ("The plan has no talker shots, so the talker would never be seen. Plan again with "
            "the talker on screen for the hook, the turns and the close.")  # fmt: skip
TOO_LONG = "The narration runs past HeyGen's 10 minutes. Shorten the script to make the talker."


def on(db: Session, project: Project) -> bool:
    """A Presenter video whose presenter talks to camera in their own room (its style's start
    for UGC, or chosen for the video: app/host.how)."""
    from app import host

    return host.on(db, project) and host.how(project) == "talks"


def minimax(db: Session, project: Project) -> bool:
    """The narration's default voice is MiniMax's (`VOICE`): a talker, or a UGC presenter in one
    spot the whole time, talking to camera or in a corner over the B-roll (Reed, 6 Nov: a talker
    in one spot is HeyGen with the MiniMax voice). A person's pick or the presenter's own saved
    voice comes first (director_song._voice)."""
    from app import host, looks

    ugc = looks.base(project.look or looks.DEFAULT) in LOOKS
    return on(db, project) or (ugc and host.on(db, project))


def _spoken(data: dict, clip_id: str) -> bool:
    """Every shot of the clip is a talker shot (`sung` on the narration's clock)."""
    timed = (data.get("song") or {}).get("shots") or {}
    ids = next((c["shot_ids"] for c in data.get("clips", []) if c["id"] == clip_id), [])
    return bool(ids) and all(timed.get(s, {}).get("sung") for s in ids)


def clips(db: Session, project: Project) -> set[str]:
    """The newest plan's talker clips: they take no take of their own."""
    from app.clip_prompts import newest

    bd = newest(db, project) if on(db, project) else None
    data = bd.data if bd else {}
    return {c["id"] for c in data.get("clips", []) if _spoken(data, c["id"])}


def where(db: Session, project: Project) -> str:
    """Where the plan puts the talker (video 281: the still said "their own room" and HeyGen
    made all three tries in a home office, for "Marcus in his parked car"): the scene of their
    first clip, its heading and its look; ROOM with none."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    data = bd.data if bd else {}
    mine = clips(db, project)
    ids = next((c["shot_ids"] for c in data.get("clips", []) if c["id"] in mine), [])  # first
    scene = next((sc for sc in data.get("scenes", []) for s in sc.get("shots", [])
                  if ids and s["id"] == ids[0]), None)  # fmt: skip
    if scene is None:
        return ROOM
    look = (scene.get("look") or "").strip()
    return f"where the plan puts them, {scene.get('heading', '').strip()}: {look}"[:400]


def frame(db: Session, project: Project) -> int | None:
    """The drawn still of the talker's first clip: where the plan puts them, as drawn."""
    from app.clip_prompts import newest
    from app.models.storyboards import StoryboardFrame

    bd, mine = newest(db, project), clips(db, project)
    first = next((c["id"] for c in (bd.data if bd else {}).get("clips", []) if c["id"] in mine),
                 None)  # fmt: skip
    return db.scalar(select(StoryboardFrame.file_id).where(
        StoryboardFrame.project_id == project.id, StoryboardFrame.breakdown_id == bd.id,
        StoryboardFrame.clip_id == first, StoryboardFrame.file_id.is_not(None))
        .order_by(StoryboardFrame.id).limit(1)) if first else None  # fmt: skip


def shot(db: Session, project: Project, shot_id: str) -> bool:
    """The shot is the talker's (one of their clips'): its picture is the talker's still."""
    from app.clip_prompts import newest

    bd, mine = newest(db, project), clips(db, project)
    return any(shot_id in c["shot_ids"] for c in (bd.data if bd else {}).get("clips", [])
               if c["id"] in mine)  # fmt: skip


def says(db: Session, project: Project, clip: ProjectClip) -> bool:
    from app.models.breakdowns import BreakdownVersion

    bd = db.get(BreakdownVersion, clip.breakdown_id or 0)
    return bool(bd) and on(db, project) and _spoken(bd.data, clip.clip_id)


def share(db: Session, project: Project) -> dict:
    """What the director reads: the talker clips, the talker's share of the screen and the
    longest stretch of talker without a cut-in (the references: 40-45% and median holds of
    3-6 s)."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    timed = ((bd.data if bd else {}).get("song") or {}).get("shots") or {}
    spans = sorted((t["start"], t["end"], bool(t.get("sung"))) for t in timed.values())
    total = max((b for _, b, _ in spans), default=0) or 1
    holds, run = [], 0.0
    for a, b, sung in spans:
        run = run + b - a if sung else 0.0
        holds.append(run)
    talking = sum(b - a for a, b, sung in spans if sung)
    return {"clips": sorted(clips(db, project)), "on_screen": round(talking / total, 2),
            "longest_hold": round(max(holds, default=0), 1)}  # fmt: skip


def whole(seconds: float) -> list[tuple[float, float]]:
    """The talker's one piece: the whole narration, within HeyGen's 10 minutes."""
    if seconds > LONGEST:
        raise ValueError(TOO_LONG)
    return [(0.0, seconds)]


def motion(note: str) -> str:
    """The director's motion note for the take (its emotion and lines: what the face, head and
    hands do, and what's in front of them), else the plain one."""
    return " ".join((note or "").split())[:LONGEST_MOTION] or MOTION


def piece_input(project: Project, row, still_file_id: int, note: str = "") -> dict:
    """The one HeyGen take: the still, and the whole narration as the voice it lip-syncs
    (`duration` is for the stand-in; HeyGen's length follows the voice). `note`: the
    director's motion note (kept in the job's input, `motion`, for a remake)."""
    from app import host

    return {"step": host.PIECE, "project_id": project.id, "host_piece_id": row.id,
            "model": MODEL, "brand_id": project.brand_id, "fit_images_to": FIT,
            "input": {"aspect_ratio": project.aspect_ratio, "resolution": RESOLUTION,
                      "expressiveness": EXPRESSIVENESS, "motion_prompt": motion(note),
                      "title": f"Brand Studio video {project.id}",
                      "duration": host._seconds(row)},
            "files": {"image": [still_file_id], "audio": [row.audio_file_id]}}  # fmt: skip


def _segment(video: bytes, start: float, end: float) -> bytes:
    """The talker's take from `start` to `end`, picture only (the narration is the sound)."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(video)
        command = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", "in.mp4", "-t",
                   f"{max(end - start, 0.1):.3f}", "-an", "-c:v", "libx264", "-pix_fmt",
                   "yuv420p", "-movflags", "+faststart", "out.mp4"]  # fmt: skip
        done = subprocess.run(command, cwd=folder, capture_output=True, timeout=300)  # noqa: S603
        if done.returncode:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()


def fill(db: Session, storage, project: Project) -> None:
    """Each talker clip's take, cut from the talker's one take (free: ffmpeg), picked and
    approved; cut again only when the talker's take is a new one."""
    from app import host, video_settings

    piece = next(iter(host.rows(db, project)[1:]), None)
    made = host._jobs(db, project).get(piece.id) if piece and piece.file_id else None
    if made is None:
        return
    whole = None
    for row in db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)):
        picked = db.get(ClipTake, row.picked_take_id) if row.picked_take_id else None
        done = picked and (picked.made_with or {}).get("talker") == piece.file_id
        if done or not row.song_slice or not says(db, project, row):
            continue
        whole = whole or storage.get(db.get(StoredFile, piece.file_id).key)
        part = _segment(whole, row.song_slice["start"], row.song_slice["end"])
        key = f"{project.workspace_id}/{uuid.uuid4().hex}"
        storage.put(key, part)
        stored = StoredFile(workspace_id=project.workspace_id, key=key, size=len(part),
                            filename=f"talker {row.clip_id}.mp4", content_type="video/mp4",
                            sha256=hashlib.sha256(part).hexdigest())  # fmt: skip
        db.add(stored)
        db.flush()
        number = db.scalar(select(func.max(ClipTake.number)).where(ClipTake.clip_id == row.id))
        sung = row.song_slice.get("sung_shots")
        take = ClipTake(clip_id=row.id, number=(number or 0) + 1, job_id=made.id,
                        file_id=stored.id, prompt=row.prompt, look=project.look,
                        made_with={**video_settings.made_with(db, project, [], MODEL, sung),
                                   "talker": piece.file_id})  # fmt: skip  # made on HeyGen
        db.add(take)
        db.flush()
        row.picked_take_id, row.file_id, row.approved = take.id, stored.id, True
    db.flush()
