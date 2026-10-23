"""Allowed upload types and a check that the first bytes really match the claimed type."""

ALLOWED_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "audio/mpeg",
    "audio/wav",
    "audio/mp4",
    "video/mp4",
    "video/webm",
}  # No SVG or HTML: they can carry scripts.


def matches(content_type: str, head: bytes) -> bool:
    """True if `head` (the first bytes of the file) looks like `content_type`."""
    match content_type:
        case "image/png":
            return head.startswith(b"\x89PNG\r\n\x1a\n")
        case "image/jpeg":
            return head.startswith(b"\xff\xd8\xff")
        case "image/gif":
            return head[:6] in (b"GIF87a", b"GIF89a")
        case "image/webp":
            return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
        case "audio/wav":
            return head[:4] == b"RIFF" and head[8:12] == b"WAVE"
        case "audio/mpeg":  # ID3 tag, or a bare MPEG frame sync
            return head.startswith(b"ID3") or (
                len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0
            )
        case "audio/mp4" | "video/mp4":
            return head[4:8] == b"ftyp"
        case "video/webm":
            return head.startswith(b"\x1a\x45\xdf\xa3")
    return False
