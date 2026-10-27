"""End on the logo (Reed, 2026-10-27): when a video's end line is the brand's call to action,
the finished video ends on the brand's real logo, made at the stitch with ffmpeg (free, no AI).
Per brand: "off", "overlay" (the logo over the end line's shot, the video unchanged under it)
or "end_card" (about 1.5 s of the logo on its own colour, added after the last clip).

The end line counts as the call to action when, in the clips' breakdown, the last spoken line
says the brand's end line (`check.ends_on`: "yes" or "near", the same test that checks the
script). Nothing else is guessed, so the same video always ends the same way."""

import io
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from app.cut_in import _even, _probe
from app.models.brands import Brand
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.files import StoredFile
from app.models.projects import Project
from app.prompts import check
from app.prompts.schemas import Breakdown

MODES = ("off", "overlay", "end_card")
CARD_SECONDS = 1.5
OVERLAY_WIDTH = 0.36  # of the frame's width
CARD_WIDTH = 0.4
OVERLAY_Y = 0.58  # the logo's centre, as a share of the height: under the face, over captions
FADE = 0.25


def cta(db: Session, project: Project, clips: list[ProjectClip]) -> tuple[int, float] | None:
    """Where the call to action starts: (index of its clip, planned seconds into that clip),
    or None when the brand has no end line or the last spoken line doesn't say it."""
    brand = db.get(Brand, project.brand_id)
    if not clips or not brand.end_line.strip():
        return None
    bd = Breakdown.model_validate(db.get(BreakdownVersion, clips[-1].breakdown_id).data)
    shots = {s.id: s for scene in bd.scenes for s in scene.shots}
    spoken = [s for scene in bd.scenes for s in scene.shots if s.line]
    if not spoken:
        return None
    last, before = spoken[-1], spoken[-2] if len(spoken) > 1 else None
    said = check.ends_on(brand.end_line, last.line, brand.name, before.line if before else "")
    if said == "no":
        return None
    alone = check.ends_on(brand.end_line, last.line, brand.name) != "no"
    first = last if alone or before is None else before  # split over the last two lines
    for n, clip in enumerate(clips):
        plan = next((c for c in bd.clips if c.id == clip.clip_id), None)
        if plan and first.id in plan.shot_ids:
            ids = plan.shot_ids[: plan.shot_ids.index(first.id)]
            return n, sum(shots[i].seconds for i in ids if i in shots)
    return None


def mode(db: Session, project: Project, clips: list[ProjectClip]) -> str:
    """How this video ends: the brand's setting when its end line is the call to action and
    it has a logo, else "off"."""
    brand = db.get(Brand, project.brand_id)
    if brand.end_logo == "off" or not brand.logo_file_id or cta(db, project, clips) is None:
        return "off"
    return brand.end_logo


def apply(db: Session, storage, project: Project, clips: list[ProjectClip],
          videos: list[bytes]) -> list[bytes]:  # fmt: skip
    """The clips' videos, ending on the logo as the brand asks (unchanged when "off")."""
    how = mode(db, project, clips)
    if how == "off":
        return videos
    brand = db.get(Brand, project.brand_id)
    logo = storage.get(db.get(StoredFile, brand.logo_file_id).key)
    if how == "end_card":
        return [*videos, card(videos[-1], logo)]
    n, start = cta(db, project, clips)
    return [*videos[:n], overlay(videos[n], logo, start, clips[n].seconds), *videos[n + 1 :]]


def _run(args: list[str], cwd: Path) -> None:
    done = subprocess.run(args, cwd=cwd, capture_output=True, timeout=600)  # noqa: S603 - fixed
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])


def _audio(path: Path) -> tuple[int, int] | None:
    """Sample rate and channels of the first audio stream, or None without sound."""
    command = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-of", "json"]
    command += ["-show_entries", "stream=sample_rate,channels", str(path)]
    done = subprocess.run(command, capture_output=True, check=True, timeout=60)  # noqa: S603
    streams = json.loads(done.stdout).get("streams") or []
    return (int(streams[0]["sample_rate"]), int(streams[0]["channels"])) if streams else None


def overlay(video: bytes, logo: bytes, start: float, planned: float) -> bytes:
    """The logo over the clip from `start` (planned seconds, scaled to the real take) to its
    end, fading in; the picture under it and the sound are unchanged."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(video)
        (folder / "logo.png").write_bytes(logo)
        w, h, fps, length = _probe(folder / "in.mp4")
        at = min(start * length / planned if planned else start, max(0.0, length - FADE))
        size = _even(w * OVERLAY_WIDTH)
        graph = (
            f"[1:v]scale={size}:-2,format=rgba,setpts=PTS-STARTPTS+{at}/TB,"
            f"fade=t=in:st={at}:d={FADE}:alpha=1[logo];"
            f"[0:v][logo]overlay=(W-w)/2:H*{OVERLAY_Y}-h/2:enable='gte(t,{at})':shortest=1,"
            "format=yuv420p[v]"
        )
        _run(["ffmpeg", "-v", "error", "-y", "-i", "in.mp4", "-loop", "1", "-framerate",
              f"{fps}", "-i", "logo.png", "-filter_complex", graph, "-map", "[v]", "-map",
              "0:a?", "-c:v", "libx264", "-c:a", "copy", "out.mp4"], folder)  # fmt: skip
        return (folder / "out.mp4").read_bytes()


def background(logo: bytes) -> str:
    """The card's colour: the logo's own corner, so a square app icon sits seamlessly."""
    image = Image.open(io.BytesIO(logo)).convert("RGBA")
    r, g, b, a = image.getpixel((0, 0))
    return f"0x{r:02x}{g:02x}{b:02x}" if a else "0x000000"


def card(last: bytes, logo: bytes) -> bytes:
    """About 1.5 s of the logo, centred on its own colour, in the last clip's size and frame
    rate, with silence when the clips have sound (so the clips join cleanly)."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "last.mp4").write_bytes(last)
        (folder / "logo.png").write_bytes(logo)
        w, h, fps, _ = _probe(folder / "last.mp4")
        sound = _audio(folder / "last.mp4")
        args = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                f"color=c={background(logo)}:s={w}x{h}:r={fps}:d={CARD_SECONDS}",
                "-i", "logo.png"]  # fmt: skip
        if sound:
            layout = "mono" if sound[1] == 1 else "stereo"
            args += ["-f", "lavfi", "-i", f"anullsrc=r={sound[0]}:cl={layout}"]
        size = _even(w * CARD_WIDTH)
        graph = f"[1:v]scale={size}:-2[l];[0:v][l]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
        args += ["-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-r", f"{fps}"]
        if sound:
            args += ["-map", "2:a", "-c:a", "aac", "-shortest"]
        _run([*args, "-t", f"{CARD_SECONDS}", "out.mp4"], folder)
        return (folder / "out.mp4").read_bytes()
