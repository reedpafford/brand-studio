"""Reference files for video models (docs/prompting/FIT.md rows 4, 13, 15): which picture is
which in the prompt, how long reference media runs, and shrinking images to the video's size."""

import io
import re
import struct

from mutagen import File as MediaFile
from PIL import Image, ImageOps

# Long side of the output video, by resolution. References bigger than this cause
# fingerprint-like textures, so images are scaled down to it (never up).
LONG_SIDE = {"480p": 854, "720p": 1280, "1080p": 1920, "4k": 3840}


def reference_lines(labels: list[tuple[str, list[int]]]) -> str:
    """'[Image1] and [Image2] are Aiden.' One line per labelled asset, in upload order."""
    lines = []
    for label, numbers in labels:
        refs = [f"[Image{n}]" for n in numbers]
        names = refs[0] if len(refs) == 1 else f"{', '.join(refs[:-1])} and {refs[-1]}"
        lines.append(f"{names} {'is' if len(refs) == 1 else 'are'} {label}.")
    return "\n".join(lines)


def bind_names(prompt: str, names: dict[str, int]) -> str:
    """Replace '@Name' with the asset's first [ImageN]; every other word stays as written."""
    for name in sorted(names, key=len, reverse=True):  # '@Aiden Sr' before '@Aiden'
        pattern = rf"@{re.escape(name)}(?![\w-])"
        prompt = re.sub(pattern, f"[Image{names[name]}]", prompt, flags=re.IGNORECASE)
    return prompt


def media_seconds(data: bytes, content_type: str) -> float | None:
    """How long a video or audio file runs, or None if we can't tell."""
    if content_type == "video/webm":
        return _webm_seconds(data)
    try:
        media = MediaFile(io.BytesIO(data))
    except Exception:  # noqa: BLE001 - unreadable file: the caller says so plainly
        return None
    return media.info.length if media is not None and media.info.length else None


def _webm_seconds(data: bytes) -> float | None:
    """WebM keeps its length in the Segment Info near the start (EBML ids 0x4489, 0x2AD7B1)."""
    head = data[: 64 * 1024]
    at = head.find(b"\x44\x89")
    if at < 0 or at + 11 > len(head) or head[at + 2] not in (0x84, 0x88):
        return None
    size = head[at + 2] & 0x0F
    (duration,) = struct.unpack(">f" if size == 4 else ">d", head[at + 3 : at + 3 + size])
    scale, s = 1_000_000, head.find(b"\x2a\xd7\xb1")
    if 0 <= s < len(head) - 12 and head[s + 3] & 0xF0 == 0x80:
        n = head[s + 3] & 0x0F
        scale = int.from_bytes(head[s + 4 : s + 4 + n], "big")
    return duration * scale / 1e9


def fit_image(data: bytes, max_side: int) -> tuple[bytes, str]:
    """Scale an image down so its long side is at most `max_side`, and re-encode it as a
    standard JPEG (or PNG if it has transparency), which also avoids Seedance's JPG 400s."""
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        rgba = img.convert("RGBA")
        if rgba.getextrema()[3][0] < 255:  # some see-through pixels
            rgba.save(out, "PNG")
            return out.getvalue(), "image/png"
        rgba.convert("RGB").save(out, "JPEG", quality=92)
        return out.getvalue(), "image/jpeg"
