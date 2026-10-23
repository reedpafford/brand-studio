"""Claude client against a mocked API (no real or paid calls)."""

import json
from decimal import Decimal

import httpx2 as httpx
import pytest
from anthropic import DefaultHttpxClient

from app.claude import MODEL, ClaudeError, ask, make_client
from app.prompts.schemas import EnhanceResult
from app.settings import Settings
from tests.helpers import claude_stream

ANSWER = {
    "suggestions": [
        {
            "id": "s1",
            "kind": "brand_screen",
            "anchor": {"line": 3, "quote": "line 3"},
            "placement": "after",
            "text": "Show the buy screen",
            "screen_id": "screen:1",
            "reason": "Required screen.",
        }
    ],
    "notes": [],
}


def suggest_enhancements(client, brand, script):
    return ask(client, system=["Base rules.", brand], prompt=script, schema=EnhanceResult)


def _reply(stop_reason="end_turn", text=json.dumps(ANSWER), **extra):
    content = [{"type": "text", "text": text}] if text else []
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": MODEL,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_read_input_tokens": 2000,
            "cache_creation_input_tokens": 0,
        },
        **extra,
    }


def _client(reply, seen):
    def handler(request):
        seen.append(request)
        body = claude_stream(
            "".join(b["text"] for b in reply["content"]),
            reply["stop_reason"],
            reply.get("stop_details"),
            reply["usage"],
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    return make_client("test-key", DefaultHttpxClient(transport=httpx.MockTransport(handler)))


def test_typed_call_with_cached_system_thinking_and_fallbacks(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://somewhere-else.example")
    seen = []
    answer = suggest_enhancements(_client(_reply(), seen), "Brand: fomo.", "line 1\nline 2\nline 3")
    assert answer.parsed.suggestions[0].kind == "brand_screen"
    # 1000 x $4 + 500 x $20 + 2000 x $0.20, per million tokens
    assert answer.cost_usd == Decimal("0.0144")
    request = seen[0]
    assert str(request.url).startswith("https://api.anthropic.com/v1/messages")
    assert request.headers["anthropic-beta"] == "server-side-fallback-2026-07-01"
    body = json.loads(request.content)
    assert body["model"] == "claude-opus-5-5" and body["fallbacks"] == "default"
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert [b.get("cache_control") for b in body["system"]] == [None, {"type": "ephemeral"}]
    assert body["stream"] is True  # long answers need streaming


def test_refusal_raises_plain_error():
    reply = _reply("refusal", text="", stop_details={"type": "refusal", "category": "cyber"})
    with pytest.raises(ClaudeError, match="declined") as err:
        suggest_enhancements(_client(reply, []), "b", "s")
    assert err.value.cost_usd == Decimal("0.0144")  # refused answers are still billed


def test_cut_off_answer_raises():
    with pytest.raises(ClaudeError, match="cut off") as err:
        suggest_enhancements(_client(_reply("max_tokens", text='{"sugg'), []), "b", "s")
    assert err.value.cost_usd  # whatever was received is still recorded


def test_key_comes_only_from_studio_env_var(monkeypatch):
    monkeypatch.setenv("STUDIO_ANTHROPIC_KEY", "from-env")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-this-one")
    assert Settings().anthropic_key.get_secret_value() == "from-env"
    assert "from-env" not in repr(Settings())  # never printed or logged


def test_missing_key_is_a_clear_error():
    with pytest.raises(ClaudeError, match="STUDIO_ANTHROPIC_KEY"):
        make_client("")


def test_long_answers_are_allowed(monkeypatch):
    """The Director's breakdowns use 32k max_tokens: the SDK refuses that without streaming."""
    seen = []
    client = _client(_reply(), seen)
    answer = ask(client, system=["Base."], prompt="p", schema=EnhanceResult, max_tokens=32000)
    assert answer.parsed and json.loads(seen[0].content)["max_tokens"] == 32000
