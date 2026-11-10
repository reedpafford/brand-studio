"""Claude client against a mocked API (no real or paid calls)."""

import json
from decimal import Decimal

import httpx2 as httpx
import pytest
from anthropic import DefaultHttpxClient

from app.claude import MODEL, UNREADABLE, ClaudeError, ask, make_client
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


def test_cut_off_and_unreadable_answers_say_which():
    with pytest.raises(ClaudeError, match="ran out of room") as err:
        suggest_enhancements(_client(_reply("max_tokens", text='{"sugg'), []), "b", "s")
    assert err.value.cost_usd  # whatever was received is still recorded
    with pytest.raises(ClaudeError, match="unreadable"):
        suggest_enhancements(_client(_reply(text='{"suggestions": 3}'), []), "b", "s")


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


def test_a_shared_prompt_is_cached_before_the_part():
    """A run's breakdown and assets are cached so its later parts read them (QA on #716)."""
    seen = []
    ask(
        _client(_reply(), seen),
        system=["Rules.", "Brand: fomo."],
        prompt='<write clips="c2">',
        schema=EnhanceResult,
        shared="<breakdown>…</breakdown>",
    )
    content = json.loads(seen[0].content)["messages"][0]["content"]
    assert [b["text"] for b in content] == ["<breakdown>…</breakdown>", '<write clips="c2">']
    assert [b.get("cache_control") for b in content] == [{"type": "ephemeral"}, None]


def test_started_is_said_once_the_answer_begins_and_the_answer_is_whole():
    """A run's other parts start once the first part's answer begins (its cache is then
    readable): reading the first event never loses any of the answer."""
    calls = []
    answer = ask(_client(_reply(), []), system=["Rules."], prompt="p", schema=EnhanceResult,
                 started=lambda: calls.append(1))  # fmt: skip
    assert calls == [1] and answer.parsed.suggestions[0].kind == "brand_screen"


def test_a_step_that_comes_back_after_5_minutes_caches_its_rules_for_an_hour():
    """Cost analysis A1: the director's turns (and take watches) come back after more than 5
    minutes while takes render, and each time the 5-minute cache had expired: its ~30k tokens
    of rules were written again. The 1-hour cache keeps them; the same words are sent. A
    1-hour write costs 2x input ($8 a million), a 5-minute one 1.25x ($5)."""
    from app.claude import PRICE_PER_MTOK, counts
    from app.providers.claude import LONG_CACHE

    seen = []
    usage = {"input_tokens": 100, "output_tokens": 10, "cache_read_input_tokens": 0,
             "cache_creation_input_tokens": 30000,
             "cache_creation": {"ephemeral_1h_input_tokens": 30000,
                                "ephemeral_5m_input_tokens": 0}}  # fmt: skip
    answer = ask(_client(_reply(usage=usage), seen), system=["Rules.", "Brand."], prompt="p",
                 schema=EnhanceResult, shared="<run/>", cache_ttl="1h")  # fmt: skip
    body = json.loads(seen[0].content)
    assert [b.get("cache_control") for b in body["system"]] == [
        None,
        {"type": "ephemeral", "ttl": "1h"},
    ]  # the rules, for an hour
    assert body["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}  # after
    assert answer.cost_usd == (Decimal(100) * 4 + Decimal(10) * 20 + 30000 * 8) / 1_000_000
    assert PRICE_PER_MTOK["cache_write_1h"] == 2 * PRICE_PER_MTOK["input"]
    assert answer.tokens == {"input": 100, "output": 10, "cache_read": 0, "cache_write": 30000,
                             "cache_write_1h": 30000, "images": 0}  # fmt: skip
    plain = ask(_client(_reply(), []), system=["Rules."], prompt="p", schema=EnhanceResult)
    assert plain.tokens["cache_read"] == 2000 and counts  # 5-minute: as before
    assert LONG_CACHE == {"director": "1h", "take_watch": "1h"}  # every other step: 5 minutes


def test_the_provider_sends_its_steps_cache_lifetime_and_keeps_the_token_counts(monkeypatch):
    from types import SimpleNamespace

    from app.providers import claude as provider

    asked = {}

    def fake_ask(client, **kw):
        asked[kw["schema"].__name__] = kw["cache_ttl"]
        parsed = SimpleNamespace(model_dump=lambda: {})
        tokens = {"input": 5, "output": 2, "cache_read": 30000, "cache_write": 0,
                  "cache_write_1h": 0, "images": 3}  # fmt: skip
        return SimpleNamespace(parsed=parsed, cost_usd=Decimal("0.05"), tokens=tokens)

    monkeypatch.setattr(provider, "ask", fake_ask)
    claude = provider.ClaudeProvider("k", client=object())
    for step in ("director", "plan"):
        out = claude.run("write-claude", {"step": step, "system": ["R."], "prompt": "p"})
        (item,) = out.usage
        assert item.tokens["cache_read"] == 30000 and item.tokens["images"] == 3
    assert asked == {"DirectorTurn": "1h", "ScenePlan": "5m"}


def _replies(texts, seen):
    """A stand-in API answering each call with the next text in turn."""

    def handler(request):
        seen.append(json.loads(request.content))
        body = claude_stream(texts[len(seen) - 1])
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    return make_client("test-key", DefaultHttpxClient(transport=httpx.MockTransport(handler)))


def test_the_director_turn_goes_without_constrained_decoding_and_is_checked_here():
    """Jobs 3234-3236, 10 Nov: Anthropic refused the director's strict schema ("The compiled
    grammar is too large"), even after #1521 shrank it. Its turn now goes without
    `output_config.format`: the schema rides in the system prompt, the JSON is read from the
    answer's text and checked against DirectorTurn here; one that doesn't fit is asked once
    more with what was wrong. Every other step stays strict."""
    from app.prompts.schemas import DirectorTurn
    from app.providers.claude import LOOSE, ClaudeProvider

    assert LOOSE == {"director"}
    seen = []
    good = '```json\n{"tool": "narration", "voice": "English_Jovialman", "why": "the brief"}\n```'
    client = _replies(['{"tool": "fly", "why": "x"}', good], seen)
    out = ClaudeProvider("k", client).run(
        "write-claude", {"step": "director", "system": ["Rules.", "Brand."], "prompt": "p"}
    )
    assert out.state == "succeeded"
    assert out.output["tool"] == "narration" and out.output["voice"] == "English_Jovialman"
    assert out.output["clip_id"] is None and out.output["redraws"] == []  # left out: defaults
    first, second = seen
    assert "format" not in first.get("output_config", {})  # no strict grammar to compile
    assert first["thinking"] == {"type": "adaptive"}
    shape = first["system"][-1]
    assert '"DirectorTurn"' in shape["text"]
    assert shape["cache_control"] == {"type": "ephemeral", "ttl": "1h"}  # cached with the rules
    assert [m["role"] for m in second["messages"]] == ["user", "assistant", "user"]
    assert "tool" in second["messages"][2]["content"]  # what was wrong, fed back
    (item,) = out.usage
    assert item.cost_usd == 2 * Decimal("0.0144")  # both calls charged

    seen = []
    with pytest.raises(ClaudeError, match="unreadable") as err:  # twice wrong: a clear failure
        ask(_replies(["no json here", '{"why": "x"}'], seen), system=["R."], prompt="p",
            schema=DirectorTurn, strict=False)  # fmt: skip
    assert len(seen) == 2 and err.value.cost_usd == 2 * Decimal("0.0144")
    assert str(err.value) == UNREADABLE  # so the director's own once-more still applies

    seen = []
    ask(_replies([json.dumps(ANSWER)], seen), system=["R."], prompt="p", schema=EnhanceResult)
    assert seen[0]["output_config"]["format"]["type"] == "json_schema"  # the rest: strict
