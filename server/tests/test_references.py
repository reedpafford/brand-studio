"""Reference helpers: media length (incl. WebM) and the [ImageN] lines."""

import struct

from app.references import bind_names, media_seconds


def test_webm_length_from_segment_info():
    info = b"\x2a\xd7\xb1\x83" + (1_000_000).to_bytes(3, "big") + b"\x44\x89\x88"
    webm = b"\x1a\x45\xdf\xa3" + b"\0" * 20 + info + struct.pack(">d", 12_500.0)
    assert media_seconds(webm, "video/webm") == 12.5
    assert media_seconds(b"\x1a\x45\xdf\xa3" + b"\0" * 20, "video/webm") is None


def test_names_become_image_numbers():
    names = {"Aiden": 1, "Aiden Sr": 4}
    assert bind_names("@Aiden Sr hugs @aiden-ish @Aiden.", names) == (
        "[Image4] hugs @aiden-ish [Image1]."
    )
