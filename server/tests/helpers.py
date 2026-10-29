"""Shared checks every resource PR should use:
- `assert_hidden`: another workspace gets 404 on each call.
- `assert_no_dollars`: an editor's responses contain no `*_usd` field anywhere.
"""

import json
import re
import struct

MP3 = b"ID3" + b"0" * 32


def _box(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", 8 + len(body)) + kind + body


def mp4(seconds: float) -> bytes:
    """A tiny MP4 that says how long it is (enough for length checks)."""
    times = struct.pack(">IIII", 0, 0, 1000, int(seconds * 1000))
    mvhd = _box(b"mvhd", bytes(4) + times + bytes(80))
    return _box(b"ftyp", b"mp42" + bytes(4) + b"mp42") + _box(b"moov", mvhd)


MP4 = mp4(5)


def assert_hidden(client, calls: list[tuple]) -> None:
    """`calls` are (method, path) or (method, path, json). Each must answer 404."""
    for method, path, *body in calls:
        r = client.request(method, path, json=body[0] if body else None)
        assert r.status_code == 404, f"{method} {path} gave {r.status_code}, expected 404"


def _usd_keys(value, where="") -> list[str]:
    if isinstance(value, dict):
        found = [f"{where}.{k}" for k in value if k.endswith("_usd")]
        return found + [x for k, v in value.items() for x in _usd_keys(v, f"{where}.{k}")]
    if isinstance(value, list):
        return [x for i, v in enumerate(value) for x in _usd_keys(v, f"{where}[{i}]")]
    return []


def assert_no_dollars(client, paths: list[str]) -> None:
    """GET each path (as an editor) and fail if any `*_usd` field appears."""
    for path in paths:
        r = client.get(path)
        assert r.status_code == 200, f"GET {path} gave {r.status_code}"
        assert not _usd_keys(r.json()), f"GET {path} sent dollars: {_usd_keys(r.json())}"


def claude_stream(
    text: str,
    stop_reason: str = "end_turn",
    stop_details: dict | None = None,
    usage: dict | None = None,
) -> bytes:
    """A Messages API streaming reply (server-sent events) carrying one text block."""
    usage = usage or {
        "input_tokens": 1000,
        "output_tokens": 500,
        "cache_read_input_tokens": 2000,
        "cache_creation_input_tokens": 0,
    }
    start = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {**usage, "output_tokens": 1},
    }
    events = [("message_start", {"type": "message_start", "message": start})]
    if text:
        events += [
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": text},
                },
            ),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ]
    delta = {"stop_reason": stop_reason, "stop_sequence": None}
    if stop_details:
        delta["stop_details"] = stop_details
    events += [
        ("message_delta", {"type": "message_delta", "delta": delta, "usage": usage}),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events).encode()


def with_sheet(db, item_id: int) -> None:
    """Give a character or place an approved house-style sheet (its first picture), as if an
    editor had made and approved one; only approved sheets reach generations."""
    from app.models.library import LibraryItem

    item = db.get(LibraryItem, item_id)
    item.sheet_file_id, item.sheet_approved = item.image_file_ids[0], True
    db.commit()


def approved_plan(db, project) -> None:
    """Give a video an approved scene plan (flows 1b: the shots are made from one), as if an
    editor had written and approved it: one card per scene, an action on every line."""
    from app import plans
    from app.models.projects import Project

    if isinstance(project, str):  # "/projects/12", as a test's url names it
        project = int(re.search(r"/projects/(\d+)", project)[1])
    project = db.get(Project, project)
    plans.by_hand(db, project, plans.script(db, project))
    for scene in project.plan["scenes"]:
        for line in scene["lines"]:
            line["action"] = "It happens, big."
    plans.approve(project, None)
    db.commit()
