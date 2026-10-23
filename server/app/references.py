"""Reference files for video models (docs/prompting/FIT.md rows 4, 13, 15): '@Name' to its
[ImageN], how long reference media runs, and shrinking images to the video's size. The
"[ImageN] is …" lines themselves are the Director's (`prompts.reference_lines`)."""

import io
import re
import struct

from mutagen import File as MediaFile
from PIL import Image, ImageOps

# Long side of the output video, by resolution. References bigger than this cause
# fingerprint-like textures, so images are scaled down to it (never up).
LONG_SIDE = {"480p": 854, "720p": 1280, "1080p": 1920, "4k": 3840}
# Decompression-bomb guard: refuse images over 40 megapixels (Pillow errors at twice this).
# A 13,000 x 13,000 PNG can be under 1 MB yet need over 1 GB once decoded.
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


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


def too_many_pixels(data: bytes) -> str | None:
    """A plain reason if the image is too large to decode safely (read from its header only),
    or unreadable; None if it's fine."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
    except Exception:  # noqa: BLE001 - any unreadable picture gets the same plain answer
        return "We couldn't read that picture."
    if w * h > MAX_PIXELS:
        return f"That picture is {w}×{h}. Use one under {MAX_PIXELS // 1_000_000} megapixels."
    return None


def fit_image(data: bytes, content_type: str, max_side: int, exact: bool) -> tuple[bytes, str]:
    """Scale an image down so its long side is at most `max_side`. `exact` images (brand
    screens, products) stay lossless: the original if it already fits, else PNG. Others are
    re-encoded as standard JPEG (PNG if see-through), which also avoids Seedance's JPG 400s."""
    with Image.open(io.BytesIO(data)) as img:
        if img.width * img.height > MAX_PIXELS:  # checked before decoding any pixels
            raise ValueError(f"Image is {img.width}x{img.height}; too large to process.")
        if exact and max(img.size) <= max_side:
            return data, content_type
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        rgba = img.convert("RGBA")
        if exact or rgba.getextrema()[3][0] < 255:  # lossless, or some see-through pixels
            rgba.save(out, "PNG")
            return out.getvalue(), "image/png"
        rgba.convert("RGB").save(out, "JPEG", quality=92)
        return out.getvalue(), "image/jpeg"
