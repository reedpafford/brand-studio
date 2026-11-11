"""The director's thinking, shown as it comes (app/thinking.py): the call's stream is heard,
kept in a small file and read for the video's page. Mocked API: no real or paid calls."""

import json

import httpx2 as httpx
from anthropic import DefaultHttpxClient

from app import thinking
from app.claude import ask, make_client
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.prompts.schemas import EnhanceResult
from tests.conftest import first_brand

ANSWER = json.dumps({"suggestions": [], "notes": []})


def _events(thought: str, text: str) -> bytes:
    """A streamed reply with a thinking block (its summary) and then the answer's text."""
    usage = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0,
             "cache_creation_input_tokens": 0}  # fmt: skip
    start = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
             "content": [], "stop_reason": None, "stop_sequence": None, "usage": usage}  # fmt: skip
    block = {"type": "thinking", "thinking": "", "signature": ""}
    events = [
        {"type": "message_start", "message": start},
        {"type": "content_block_start", "index": 0, "content_block": block},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "thinking_delta", "thinking": thought},
        },  # fmt: skip
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "signature_delta", "signature": "sig"},
        },  # fmt: skip
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": text}},
        {"type": "content_block_stop", "index": 1},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": usage,
        },  # fmt: skip
        {"type": "message_stop"},
    ]
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _client(seen, refuse_shown=False):
    def handler(request):
        seen.append(json.loads(request.content))
        if refuse_shown and seen[-1]["thinking"].get("display"):
            error = {"type": "error", "error": {"type": "invalid_request_error", "message": "no"}}
            return httpx.Response(400, json=error)
        body = _events("The hook has to be the alarm.", ANSWER)
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    return make_client("test-key", DefaultHttpxClient(transport=httpx.MockTransport(handler)))


def _ask(client, live=None):
    return ask(client, system=["Rules."], prompt="a script", schema=EnhanceResult, live=live)


def test_a_call_that_is_shown_asks_for_its_thinking_and_tells_it_as_it_comes():
    seen, heard = [], []
    answer = _ask(_client(seen), live=lambda kind, words: heard.append((kind, words)))
    assert answer.parsed.suggestions == []  # the same answer, read the same way
    assert seen[0]["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert heard == [("thinking", "The hook has to be the alarm."), ("text", ANSWER)]


def test_a_call_that_is_not_shown_is_asked_as_it_always_was():
    seen = []
    _ask(_client(seen))
    assert seen[0]["thinking"] == {"type": "adaptive"}


def test_a_refused_way_of_showing_is_asked_again_without_and_a_broken_view_never_stops_it():
    seen = []

    def broken(kind, words):
        raise RuntimeError("the page's file is gone")

    assert _ask(_client(seen, refuse_shown=True), live=broken).parsed.notes == []
    assert [body["thinking"].get("display") for body in seen] == ["summarized", None]
    assert _ask(_client([]), live=broken).parsed.notes == []  # heard, failed, answered anyway


def test_the_plan_so_far_is_read_from_its_unfinished_json():
    text = ('{"treatment": {"hook": "A siren and a white van pulling away.", "logline": "A girl '
            'nearly taken \\"buying eggs\\".", "why_it_holds": "We start at the', )[0]  # fmt: skip
    assert thinking.written(text) == [
        "Hook: A siren and a white van pulling away.",
        'Story: A girl nearly taken "buying eggs".',
    ]
    more = ' end"}, "clips": [{"id": "c1", "name": "The lot", "purpose": "hook"}, '
    clips = text + more + '{"id": "c2", "name": "Aisle'
    assert thinking.written(clips)[2:] == ["Clip 1: The lot"]  # c2's name isn't whole yet
    assert thinking.written("") == [] and thinking.written("not json") == []


def test_the_file_holds_the_last_of_the_thinking_and_goes_when_the_call_ends(tmp_path, monkeypatch):
    monkeypatch.setattr(thinking, "_path", lambda job_id: tmp_path / "thinking" / f"{job_id}.json")
    monkeypatch.setattr(thinking, "EVERY", 0)
    assert thinking.read(7) is None  # nothing said yet
    writer = thinking.Writer(7)
    writer("thinking", "x" * (thinking.TAIL + 50) + " and the end")
    writer("text", '{"treatment": {"hook": "Eggs hit the asphalt."')
    said = thinking.read(7)
    assert said["thinking"].endswith(" and the end") and len(said["thinking"]) == thinking.TAIL
    assert said["written"] == ["Hook: Eggs hit the asphalt."]
    writer.close()
    assert thinking.read(7) is None and not list((tmp_path / "thinking").iterdir())


def test_the_page_reads_it_only_while_the_plan_call_runs(owner, db, tmp_path, monkeypatch):
    monkeypatch.setattr(thinking, "_path", lambda job_id: tmp_path / f"{job_id}.json")
    monkeypatch.setattr(thinking, "EVERY", 0)
    brand = first_brand(owner)
    project = owner.post("/projects", json={"brand_id": brand, "name": "T"}).json()["id"]
    url = f"/projects/{project}/director/thinking"
    assert owner.get(url).json() is None  # no call running
    workspace = db.get(Project, project).workspace_id
    job = Job(workspace_id=workspace, kind="write", provider="claude", project_id=project,
              brand_id=brand, input={"step": "one_pass"}, status=JobStatus.running)  # fmt: skip
    db.add(job)
    db.commit()
    assert owner.get(url).json() is None  # running, nothing said yet
    thinking.Writer(job.id)("thinking", "Start on the siren.")
    assert owner.get(url).json() == {"thinking": "Start on the siren.", "written": []}
    job.status = JobStatus.succeeded
    db.commit()
    assert owner.get(url).json() is None  # its answer is in: the plan itself shows


def test_the_worker_shows_only_the_plan_call_and_clears_up(app, db, editor, tmp_path, monkeypatch):
    from app.models.accounts import User
    from tests.test_enhance import FakeClaude, _run

    monkeypatch.setattr(thinking, "_path", lambda job_id: tmp_path / f"{job_id}.json")
    monkeypatch.setattr(thinking, "EVERY", 0)
    wrote = []
    write = thinking.Writer._write
    monkeypatch.setattr(thinking.Writer, "_write", lambda self: (write(self), wrote.append(1)))
    me = db.query(User).filter_by(email=editor.get("/auth/me").json()["email"]).one()

    def ran(shown: bool):
        monkeypatch.setattr(thinking, "STEPS", {"change"} if shown else {"one_pass"})
        job = Job(workspace_id=me.workspace_id, created_by_id=me.id, kind="write-claude",
                  provider="claude", input={"step": "change", "system": ["Check it."],
                  "prompt": "Does it fit?"})  # fmt: skip
        db.add(job)
        db.commit()
        fake = FakeClaude({"prompt": "fits"})
        _run(app, db, fake)
        assert db.get(Job, job.id).output["prompt"] == "fits"  # answered, as in test_worker
        return fake.requests[0]["thinking"]

    assert ran(False) == {"type": "adaptive"} and not wrote  # any other step: as it always was
    assert ran(True) == {"type": "adaptive", "display": "summarized"} and wrote
    assert not list(tmp_path.glob("*.json"))  # the call ended: nothing left behind
