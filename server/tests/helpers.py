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
        found = [f"{where}.{k}" for k, v in value.items()
                 if k.endswith("_usd") or (k == "usd" and v is not None)]  # fmt: skip
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


def shot(db, **change) -> None:
    """Change the first shot of the video's breakdown (what a take or still shows)."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.breakdowns import BreakdownVersion

    row = db.query(BreakdownVersion).order_by(BreakdownVersion.id.desc()).first()
    row.data["scenes"][0]["shots"][0].update(change)
    flag_modified(row, "data")
    db.commit()


def product(db, brand_id: int, name: str) -> int:
    """The brand's library product of that name (made when it has none), for a picture's
    product_id."""
    from app.models.brands import Brand
    from app.seed import product_of

    return product_of(db, db.get(Brand, brand_id), name)


def moves(db, project_id: int) -> list[str]:
    """Each of the video's director turns, every run, as its log says it: what it did (a
    delivery, its reason). The chat shows one card a run instead (app/run_progress)."""
    from app import run_progress
    from app.models.projects import Project

    every = run_progress.runs(db, db.get(Project, project_id)).values()
    note = lambda o: " ".join(o.get(k) or "" for k in ("made", "unsure", "needs")).strip()  # noqa: E731
    return [(note(j.output) or j.output.get("why", "")) if (j.output or {}).get("tool") == "deliver"
            else j.input.get("result", "") for turns in every for j in turns]  # fmt: skip


def make_it(db) -> int:
    """Press Make it, as the owner, on every start card waiting (S3-02): the run goes on past
    its treatment. How many were pressed."""
    from app import asks
    from app.models.accounts import Role, User
    from app.models.asks import Ask

    pressed = 0
    for ask in db.query(Ask).filter_by(kind="start", state="open").all():
        if asks.state(db, ask) == "open":
            owner = db.query(User).filter_by(workspace_id=ask.workspace_id, role=Role.owner)
            asks.answer(db, owner.first(), ask, {"how": "make_it"})
            pressed += 1
    return pressed


def approve_cast(client, project) -> dict:
    """Approve cast & places as the person making the video does: the whole set as shown in
    Cast (app/cast_gate.py), so the stills and takes that wait for it can be made."""
    if isinstance(project, str):  # "/projects/12", as a test's url names it
        project = int(re.search(r"/projects/(\d+)", project)[1])
    shown = client.get(f"/projects/{project}/cast").json()
    seen = {i["ref"]: i["sig"] for i in shown["items"]}
    done = client.post(f"/projects/{project}/cast/approve", json={"seen": seen})
    assert done.status_code == 200 or shown["state"] in ("none", "approved"), done.text
    return done.json()


def ok_when_asked(db) -> None:
    """The person a director run belongs to approves its cast and places once it waits on
    them (director.CAST_WAIT), as they would in Cast after looking: the whole set as shown."""
    from app import cast_gate, director
    from app.models.accounts import User
    from app.models.jobs import Job
    from app.models.projects import Project

    step = Job.input["step"].as_string()
    waiting: dict[int, Job] = {}  # each video once, by its first turn waiting on it (reading
    for job in db.query(Job).filter(step == director.STEP).order_by(Job.id).all():  # is slow)
        if job.input.get("result") == director.CAST_WAIT and not job.input.get("ended"):
            waiting.setdefault(job.project_id, job)
    for job in waiting.values():
        project = db.get(Project, job.project_id)
        items = cast_gate.current(db, project)  # pending: any item not approved as it is
        if any(i["approval"] != "approved" for i in items) and all(
            i["readiness"] == "ready" for i in items
        ):
            who = db.get(User, job.input[director.RUN]["by"])
            cast_gate.approve(db, who, project, {i["ref"]: i["sig"] for i in items})
