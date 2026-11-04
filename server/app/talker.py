"""The UGC talker (Reed, 3 Nov: "Heygen for still imaged UGC talking, yes."). In a Presenter
video in the UGC style the host isn't keyed into a corner: one still of the talker in their own
room, then ONE HeyGen Avatar IV take of the whole narration (the MiniMax voice with its room
sound, app/room.py), lip-synced from that still (app/host.py makes both, priced like takes). The
plan's talker shots (in a narration, `sung`: the talker says that stretch to the lens) are cut
from that take at the final cut; every other shot is B-roll cut in over the voice, so the cut
alternates talker and B-roll. Settings from HeyGen's docs and the batch-b test
(.context/team/research/ugc-realism.md): type image, 720p, expressiveness medium, a motion
prompt that keeps the talker in place and the phone locked off."""

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

LOOKS = ("ugc",)  # the styles whose host is a talker on HeyGen
MODEL, RESOLUTION, PROVIDER = "heygen-avatar-iv", "720p", "heygen"
VOICE = narration.MINIMAX_VOICES[0]  # a talker's voice when the director names none
LONGEST = 600.0  # HeyGen: an avatar's audio input runs 10 minutes at most
FIT = 1920  # HeyGen takes images under 2K: "as much resolution as you have"
STILL_PROMPT = (
    "{who}, filmed by themselves on their phone: chest-up, centred, facing the camera at eye "
    "level and looking straight into the lens, the whole head and both shoulders in frame with "
    "a little space above the head, a relaxed, natural expression, the mouth closed or just "
    "parted. Nothing covers the face: no sunglasses, no hat brim, no hand near the mouth. They "
    "are in their own real, lived-in room that says who they are, in focus behind them, lit by "
    "soft window daylight from the front. A real vertical phone photo, unretouched: natural "
    "skin with pores, no studio light, no shallow-focus blur, only this one person in it."
)  # HeyGen: a clear, front-facing, evenly lit portrait, the whole head in frame, one person
MOTION = (
    "They stay where they are and talk straight into the phone lens like a real selfie video: "
    "small natural head nods and tilts, blinks, eyebrows that move with the words, and now and "
    "then one easy hand gesture low in the frame. The phone is locked off: no camera movement."
)
SAID = "The talker says this clip: its picture is cut from the talker's take. Make the host."
NO_SHOTS = ("The plan has no talker shots, so the talker would never be seen. Plan again with "
            "the talker on screen for the hook, the turns and the close.")  # fmt: skip
TOO_LONG = "The narration runs past HeyGen's 10 minutes. Shorten the script to make the talker."


def on(db: Session, project: Project) -> bool:
    """A Presenter video in a talker's style."""
    from app import host

    return project.look in LOOKS and host.on(db, project)


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


def piece_input(project: Project, row, still_file_id: int) -> dict:
    """The one HeyGen take: the still, and the whole narration as the voice it lip-syncs
    (`duration` is for the stand-in; HeyGen's length follows the voice)."""
    from app import host

    return {"step": host.PIECE, "project_id": project.id, "host_piece_id": row.id,
            "model": MODEL, "brand_id": project.brand_id, "fit_images_to": FIT,
            "input": {"aspect_ratio": project.aspect_ratio, "resolution": RESOLUTION,
                      "expressiveness": "medium", "motion_prompt": MOTION,
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
    from app.breakdown import video_model

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
                        made_with={**video_settings.made_with(db, project, [],
                                                              video_model(project).id, sung),
                                   "talker": piece.file_id})  # fmt: skip
        db.add(take)
        db.flush()
        row.picked_take_id, row.file_id, row.approved = take.id, stored.id, True
    db.flush()
