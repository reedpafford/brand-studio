"""Cut-ins at stitch time (free, ffmpeg): an insert shot's stretch of the generated clip is
replaced by the real brand picture, so screens and products show exactly (Seedance can't
promise exact text). Any shot that shows a brand screen can have it, characters or not (screens
are in the character's hand, Director #546). The editor can switch each one on; all start off
(Reed, 2026-10-27: screens and products may be generated, as long as the logo is right).

The picture is fitted inside the frame over the clip itself, blurred, with a slow push in
(about 3% over the shot). It stays up at least 1.2 s. The clip's audio is unchanged."""

import io
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from app.enhance import project_screens, screen_name
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.projects import Project

MIN_SECONDS = 1.2
PUSH_IN = 0.03
FILL = 0.9  # the picture's share of the frame's width or height


@dataclass
class Insert:
    shot_id: str
    asset_id: str  # screen:N
    name: str
    file_id: int
    start: float  # seconds into the clip, as planned (scaled to the real take when stitching)
    end: float
    on: bool


def inserts(db: Session, project: Project, clip: ProjectClip) -> list[Insert]:
    """The clip's shots that show one of this project's screens (its first), in order."""
    bd = db.get(BreakdownVersion, clip.breakdown_id).data
    shots = {s["id"]: s for scene in bd["scenes"] for s in scene["shots"]}
    ids = next((c["shot_ids"] for c in bd["clips"] if c["id"] == clip.clip_id), [])
    screens = {f"screen:{s.id}": s for s in project_screens(db, project)}
    total = sum(shots[i]["seconds"] for i in ids if i in shots) or 1
    scale, at, out = clip.seconds / total, 0.0, []
    for shot_id in ids:
        shot = shots.get(shot_id, {"seconds": 0})
        start, at = at, at + shot["seconds"] * scale
        first = next((i for i in shot.get("screen_ids") or [] if i in screens), None)
        if first is None:
            continue
        screen = screens[first]
        on = (clip.real_images or {}).get(shot_id, False)
        out.append(Insert(shot_id, first, screen_name(screen), screen.file_id, start, at, on))
    return out


def still_shown(old: dict, new: dict, real_images: dict) -> dict:
    """ "Use the real image" kept only for shots the new breakdown has as they were, showing
    the same thing (Reed, 2026-10-27: it's cleared when its shot is replaced)."""

    def shots(bd: dict) -> dict:
        return {s["id"]: (s.get("action"), s.get("screen_ids") or [])
                for scene in bd.get("scenes") or [] for s in scene.get("shots") or []}  # fmt: skip

    was, now = shots(old or {}), shots(new or {})
    return {k: on for k, on in real_images.items() if k in now and was.get(k) == now[k]}


def _probe(path: Path) -> tuple[int, int, float, float]:
    """Width, height, frame rate and length of a video."""
    entries = "stream=width,height,r_frame_rate:format=duration"
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-of", "json"]
    command += ["-show_entries", entries, str(path)]
    done = subprocess.run(command, capture_output=True, check=True, timeout=60)  # noqa: S603
    found = json.loads(done.stdout)
    stream = found["streams"][0]
    num, den = stream["r_frame_rate"].split("/")
    fps = float(num) / float(den or 1) or 24.0
    return stream["width"], stream["height"], fps, float(found["format"]["duration"])


def _even(n: float) -> int:
    return max(2, int(n) // 2 * 2)


def apply(video: bytes, cuts: list[tuple[bytes, float, float]], planned: float) -> bytes:
    """Put each picture over its (start, end) stretch of the clip. Times are planned seconds,
    scaled to the clip's real length."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(video)
        w, h, fps, length = _probe(folder / "in.mp4")
        scale = length / planned if planned else 1
        pads = "".join(f"[b{i}]" for i in range(1, len(cuts) + 1))
        args, chains = ["-i", "in.mp4"], [f"[0:v]split={len(cuts) + 1}[v0]{pads}"]
        for i, (picture, start, end) in enumerate(cuts, 1):
            start, end = start * scale, max(end * scale, start * scale + MIN_SECONDS)
            start, end = max(0.0, min(start, length - MIN_SECONDS)), min(end, length)
            with Image.open(io.BytesIO(picture)) as img:
                fit = min(w * FILL / img.width, h * FILL / img.height)
                pw, ph = _even(img.width * fit), _even(img.height * fit)
                img.convert("RGB").save(folder / f"{i}.png")
            frames = max(1, round((end - start) * fps))
            args += ["-loop", "1", "-framerate", f"{fps}", "-t", f"{end - start}", "-i", f"{i}.png"]
            zoom = f"1+{PUSH_IN}*on/{frames}"
            chains += [
                f"[{i}:v]scale={pw * 2}:{ph * 2},zoompan=z='{zoom}':d=1:s={pw}x{ph}:fps={fps}"
                f":x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2',setpts=PTS-STARTPTS+{start}/TB[p{i}]",
                f"[b{i}]boxblur=lr='min(w,h)/10':lp=2:cr='min(cw,ch)/10':cp=2[g{i}]",
                f"[g{i}][p{i}]overlay=(W-w)/2:(H-h)/2:eof_action=pass[c{i}]",
                f"[v{i - 1}][c{i}]overlay=0:0:enable='between(t,{start},{end})'[v{i}]",
            ]
        command = ["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", ";".join(chains)]
        command += ["-map", f"[v{len(cuts)}]", "-map", "0:a?", "-c:v", "libx264"]
        command += ["-pix_fmt", "yuv420p", "-c:a", "copy", "out.mp4"]
        done = subprocess.run(command, cwd=folder, capture_output=True, timeout=600)  # noqa: S603
        if done.returncode:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()
