"""Claude client for Enhance and breakdowns (prompts come with the script issue).

- Model claude-opus-5-5 with adaptive thinking and structured output (Pydantic), streamed
  (so long answers don't hit the SDK's non-streaming time limit).
- The fixed system prompt (base + brand) is cached: it's identical on every call for a brand.
- Server-side fallbacks are on: a policy decline is retried on Anthropic's recommended model.
- Key only from STUDIO_ANTHROPIC_KEY; always https://api.anthropic.com (ANTHROPIC_BASE_URL in
  the environment is ignored on purpose)."""

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from anthropic import Anthropic, DefaultHttpxClient
from pydantic import BaseModel, ValidationError

MODEL = "claude-opus-5-5"
API_URL = "https://api.anthropic.com"
# Opus 5.5's answer room at most (Anthropic: 128K output tokens, streamed). Adaptive thinking
# counts against a call's max_tokens, so a long script's steps get more (long scripts, 10 Nov);
# only what is used is charged. No call asks past this.
MOST_TOKENS = 128_000
ROOM = 32_000  # a call's room unless its step sets one
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Claude Opus 5.5, USD per million tokens. Cache writes cost 1.25x input for the 5-minute
# lifetime and 2x for the 1-hour one; reads 0.05x.
PRICE_PER_MTOK = {
    "input": Decimal(4),
    "output": Decimal(20),
    "cache_read": Decimal("0.20"),
    "cache_write": Decimal(5),
    "cache_write_1h": Decimal(8),
}
# Each model a step may be asked on, at its own price. Claude Sonnet 5.5 (the one-pass plan
# can be set to it: BS_ONE_PASS_MODEL): $2 in, $10 out and $0.10 a cache read per million
# tokens (Anthropic's model table, as of 3 Nov 2026); its cache writes by the same multiples
# of its input price as above (1.25x and 2x).
PRICES = {
    MODEL: PRICE_PER_MTOK,
    "claude-sonnet-5-5": {
        "input": Decimal(2),
        "output": Decimal(10),
        "cache_read": Decimal("0.10"),
        "cache_write": Decimal("2.50"),
        "cache_write_1h": Decimal(4),
    },
}


def price_ratio(model: str) -> Decimal:
    """What a call on `model` costs beside the same call on the usual one (MODEL), by their
    output price: a step's flat estimate, made for the usual model, scales by it."""
    return PRICES[model]["output"] / PRICE_PER_MTOK["output"]


log = logging.getLogger(__name__)

RAN_OUT = "Claude's answer ran out of room (the output limit) before it was finished."
UNREADABLE = "Claude's answer came back unreadable (not the shape asked for)."


class ClaudeError(Exception):
    """Claude couldn't give a usable answer (refused, or ran out of room). `cost_usd` is what
    the call still cost (None if unknown), so it can be recorded as usage."""

    def __init__(self, message: str, cost_usd: Decimal | None = None):
        super().__init__(message)
        self.cost_usd = cost_usd


@dataclass
class Answer[T: BaseModel]:
    parsed: T
    model: str  # the model that answered (a fallback may have served it)
    cost_usd: Decimal  # owner-only, like all dollar amounts
    tokens: dict | None = None  # input, output, cache_read, cache_write, images (`counts`)


def make_client(key: str, http_client=None) -> Anthropic:
    if not key:
        raise ClaudeError("STUDIO_ANTHROPIC_KEY is not set.")
    return Anthropic(
        api_key=key,
        base_url=API_URL,
        http_client=http_client or DefaultHttpxClient(),
    )


def ask[T: BaseModel](
    client: Anthropic,
    *,
    system: list[str],
    prompt: str,
    schema: type[T],
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "high",
    max_tokens: int = ROOM,
    images: Sequence[str] = (),
    shared: str = "",
    cache_ttl: Literal["5m", "1h"] = "5m",
    started: Callable[[], None] | None = None,
    strict: bool = True,
    model: str = MODEL,
) -> Answer[T]:
    """One structured call. `system` is the fixed parts (base prompt, then the brand's);
    the cache mark on the last part caches them all together. `images` (data URLs) go
    before the prompt, for a check that looks at a picture. `shared` (a run's breakdown and
    assets) goes first and is cached too, so a run's later parts read it. `cache_ttl` "1h":
    the fixed parts stay cached an hour, for a step that comes back after more than 5 minutes
    (the director's turns while takes render): the same words, a dearer first write (2x
    against 1.25x), and no re-write on each later call. `started` is called once the answer
    begins (its first streamed event): the cache it writes can be read from then on.
    `strict` False: no constrained decoding (for a schema too complex for Anthropic's grammar
    limit, the director's): the schema goes in the system prompt, the answer is JSON in text,
    checked here against `schema`, and asked once more with the problems if it doesn't fit.
    `model`: the model asked (one of PRICES); the call is costed at that model's price."""
    max_tokens = min(max_tokens, MOST_TOKENS)
    blocks = [{"type": "text", "text": text} for text in system]
    if not strict:
        blocks.append({"type": "text", "text": SHAPE + json.dumps(schema.model_json_schema())})
    content = [_image(url) for url in images] + [{"type": "text", "text": prompt}]
    if shared:
        cached = {"type": "text", "text": shared, "cache_control": {"type": "ephemeral"}}
        content = [cached, *content]
    blocks[-1]["cache_control"] = (
        {"type": "ephemeral", "ttl": "1h"} if cache_ttl == "1h" else {"type": "ephemeral"}
    )  # an hour-long entry before the 5-minute `shared` one, as the API requires
    messages = [{"role": "user", "content": content if images or shared else prompt}]
    if not strict:
        return _loose(client, schema, started, len(images), messages=messages, model=model,
                      max_tokens=max_tokens, system=blocks, effort=effort)  # fmt: skip
    # Streamed: long answers (breakdowns) can take longer than the SDK allows unstreamed.
    with client.beta.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=blocks,
        messages=messages,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        output_format=schema,
        betas=[FALLBACK_BETA],
        fallbacks="default",
    ) as stream:
        try:
            if started:
                next(stream, None)  # the first event: the prompt is read and cached by now
                started()
            response = stream.get_final_message()
        except ValidationError as exc:  # the JSON was cut off (max_tokens) or malformed
            cut = any("EOF" in e["msg"] for e in exc.errors())  # the JSON stops mid-way
            raise ClaudeError(RAN_OUT if cut else UNREADABLE, _cost_so_far(stream, model)) from exc
    cost, tokens = _cost(response.usage, model), counts(response.usage, len(images))
    if response.stop_reason == "refusal":
        category = response.stop_details.category if response.stop_details else None
        raise ClaudeError(f"Claude declined this request ({category or 'no category'}).", cost)
    if response.stop_reason == "max_tokens":
        raise ClaudeError(RAN_OUT, cost)
    if response.parsed_output is None:
        raise ClaudeError(UNREADABLE, cost)
    return Answer(response.parsed_output, response.model, cost, tokens)


SHAPE = (
    "Answer with one JSON object that matches this JSON schema, and nothing else (no words "
    "before or after it, no code fence):\n"
)


def _loose[T: BaseModel](
    client: Anthropic, schema: type[T], started, images: int, *, messages: list,
    max_tokens: int, system: list, effort: str, model: str = MODEL,
) -> Answer[T]:  # fmt: skip
    """`ask` without constrained decoding: the answer's JSON is read from its text and checked
    against `schema` (fields left out take their defaults). One that doesn't fit is asked once
    more, with what was wrong; a second miss is UNREADABLE. Both calls are charged."""
    cost, tokens = Decimal(0), {}
    for attempt in (1, 2):
        with client.beta.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            if started and attempt == 1:
                next(stream, None)  # the first event: the prompt is read and cached by now
                started()
            response = stream.get_final_message()
        cost += _cost(response.usage, model)
        for key, n in counts(response.usage, images).items():
            tokens[key] = tokens.get(key, 0) + n
        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise ClaudeError(f"Claude declined this request ({category or 'no category'}).", cost)
        if response.stop_reason == "max_tokens":
            raise ClaudeError(RAN_OUT, cost)
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        try:
            return Answer(schema.model_validate(_json(text)), response.model, cost, tokens)
        except (ValueError, ValidationError) as exc:
            problems = _problems(exc)
            log.warning("Claude's answer didn't fit %s (try %d): %s", schema.__name__, attempt,
                        problems)  # fmt: skip
        messages = [
            *messages,
            {"role": "assistant", "content": text or "(no answer)"},
            {"role": "user", "content": f"That answer doesn't fit the JSON schema: {problems}. "
             "Send the whole answer again, fixed, as one JSON object and nothing else."},
        ]  # fmt: skip
    raise ClaudeError(UNREADABLE, cost)  # exactly UNREADABLE: the director's own retry applies


def _json(text: str):
    """The JSON object in an answer's text (a code fence or words around it are dropped)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the answer")
    return json.loads(text[start : end + 1])


def _problems(exc: Exception) -> str:
    """What was wrong with an answer, short enough to send back."""
    if not isinstance(exc, ValidationError):
        return str(exc)
    return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'answer'}: {e['msg']}"
                     for e in exc.errors()[:20])  # fmt: skip


def _image(url: str) -> dict:
    """A data URL ("data:image/png;base64,…") as an image block."""
    head, data = url.split(",", 1)
    media = head.removeprefix("data:").split(";")[0]
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}


def _cost_so_far(stream, model: str = MODEL) -> Decimal | None:
    try:
        return _cost(stream.current_message_snapshot.usage, model)
    except AssertionError:  # nothing received yet
        return None


def _writes(usage) -> tuple[int, int]:
    """(5-minute, 1-hour) cache-write tokens; all 5-minute when the breakdown is missing."""
    split = getattr(usage, "cache_creation", None)
    long = (getattr(split, "ephemeral_1h_input_tokens", 0) or 0) if split else 0
    return (usage.cache_creation_input_tokens or 0) - long, long


def _cost(usage, model: str = MODEL) -> Decimal:
    """What a call cost, at the price of the model it was asked on."""
    short, long = _writes(usage)
    tokens = {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "cache_read": usage.cache_read_input_tokens or 0,
        "cache_write": short,
        "cache_write_1h": long,
    }
    return sum((Decimal(n) * PRICES[model][k] / 1_000_000 for k, n in tokens.items()), Decimal(0))


def counts(usage, images: int = 0) -> dict:
    """A call's token counts as Usage keeps them (A8): what it read, wrote, read from and wrote
    to the cache, and the pictures it was sent."""
    short, long = _writes(usage)
    return {"input": usage.input_tokens or 0, "output": usage.output_tokens or 0,
            "cache_read": usage.cache_read_input_tokens or 0, "cache_write": short + long,
            "cache_write_1h": long, "images": images}  # fmt: skip
