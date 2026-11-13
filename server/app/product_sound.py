"""A product's own sound in the cut (Movie Ad 1, Reed, 13 Nov 2026: the alarm "needs to die
down very quickly after, or be muffled while the dialogue goes over it ... It should turn off
when the light goes off"). The sound is kept on the product in the brand's library (its
`voice_file_id`); the plan marks the shots it is heard in (`product_sound`); the cut lays it
over those stretches of the take: loud, down under every spoken word, and off the moment the
last marked shot ends. `of_take`: what a take's cut needs; `apply`: the mix (ffmpeg, free)."""

import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.clips import ClipTake, ProjectClip
from app.models.files import StoredFile
from app.models.library import Kind, LibraryItem
from app.models.projects import Project

LOUD, UNDER = 3.0, -15.0  # LU against the voice: on its own (over the voice), and under a line
OWN = 0.5  # the take's own sound while the product's is loud (the model's guess at it)
ON, DIP = 0.05, 0.25  # seconds: it starts and stops with its picture; it dips under a line


def of_take(db: Session, project: Project, row: ProjectClip, take: ClipTake) -> dict | None:
    """{key, spans, speech} for a take whose plan has shots the product is heard in, when a
    product of the clip (else of the video) has a sound; None otherwise."""
    from app import one_pass
    from app.cut import spoken
    from app.models.breakdowns import BreakdownVersion
    from app.word_splice import _heard

    plan = (db.get(BreakdownVersion, row.breakdown_id).data or {}).get(one_pass.PLAN) or {}
    clip = next((c for c in plan.get("clips") or [] if c.get("id") == row.clip_id), None)
    spans, at = [], 0.0
    for shot in (clip or {}).get("shots") or []:
        end = at + float(shot.get("seconds") or 0)
        if shot.get("product_sound"):
            if spans and spans[-1][1] == at:
                spans[-1][1] = end
            else:
                spans.append([at, end])
        at = end
    ids = [int(a[5:]) for a in (clip or {}).get("assets") or [] if a.startswith("prop:")]
    items = [db.get(LibraryItem, i) for i in [*ids, *(project.product_ids or [])]]
    item = next((i for i in items if i and i.kind == Kind.prop and i.voice_file_id), None)
    if not spans or item is None:
        return None
    return {"key": db.get(StoredFile, item.voice_file_id).key, "spans": spans,
            "speech": spoken(_heard(db, take)[0])}  # fmt: skip


def _during(spans: list, ramp: float) -> str:
    """1 inside the spans, 0 outside, ramped over `ramp` seconds at each edge."""
    out = ""
    for a, b in spans:
        one = f"clip(min((t-{a - ramp:.2f})/{ramp},({b + ramp:.2f}-t)/{ramp}),0,1)"
        out = f"max({out},{one})" if out else one
    return out or "0"


def apply(video: bytes, sound: bytes, spans: list, speech: list) -> bytes:
    """The take with the product's sound over `spans` (seconds in the take), looped to fill
    them: at LOUD against the voice, at UNDER while someone speaks (`speech`), the take's own
    sound halved under it; the picture copied as it is."""
    from app.cut_render import _probe
    from app.take_sound import CEILING, gain, measured

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(video)
        (folder / "sound").write_bytes(sound)
        loud = 10 ** (gain(measured(folder, "sound"), LOUD) / 20)
        dip = 1 - 10 ** ((UNDER - LOUD) / 20)
        on, said = _during(spans, ON), _during(speech, DIP)
        ours = (f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=eval=frame:"
                f"volume='{loud:.4f}*{on}*(1-{dip:.4f}*{said})',"
                f"alimiter=limit={CEILING:.3f}:level=disabled")  # fmt: skip
        if _probe(folder, "in.mp4", "a:0", "index"):
            graph = (f"{ours}[s];[0:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                     f"volume=eval=frame:volume='1-{1 - OWN}*{on}*(1-{said})'[o];"
                     "[o][s]amix=inputs=2:normalize=0:duration=first[a]")  # fmt: skip
        else:
            graph = f"{ours}[a]"
        command = ["ffmpeg", "-v", "error", "-y", "-i", "in.mp4", "-stream_loop", "-1", "-i",
                   "sound", "-filter_complex", graph, "-map", "0:v", "-map", "[a]", "-c:v",
                   "copy", "-c:a", "aac", "-shortest", "out.mp4"]  # fmt: skip
        done = subprocess.run(command, cwd=folder, capture_output=True, timeout=600)  # noqa: S603
        if done.returncode != 0:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()
