"""Claude client for Enhance and breakdowns (prompts come with the script issue).

- Model claude-opus-5-5 with adaptive thinking and structured output (Pydantic), streamed
  (so long answers don't hit the SDK's non-streaming time limit).
- The fixed system prompt (base + brand) is cached: it's identical on every call for a brand.
- Server-side fallbacks are on: a policy decline is retried on Anthropic's recommended model.
- Key only from STUDIO_ANTHROPIC_KEY; always https://api.anthropic.com (ANTHROPIC_BASE_URL in
  the environment is ignored on purpose)."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from anthropic import Anthropic, DefaultHttpxClient
from pydantic import BaseModel, ValidationError

MODEL = "claude-opus-5-5"
API_URL = "https://api.anthropic.com"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Claude Opus 5.5, USD per million tokens. Cache writes (5 min) cost 1.25x input.
PRICE_PER_MTOK = {
    "input": Decimal(4),
    "output": Decimal(20),
    "cache_read": Decimal("0.20"),
    "cache_write": Decimal(5),
}


CUT_OFF = "Claude's answer was cut off or unreadable."


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
    max_tokens: int = 16000,
    images: Sequence[str] = (),
) -> Answer[T]:
    """One structured call. `system` is the fixed parts (base prompt, then the brand's);
    the cache mark on the last part caches them all together. `images` (data URLs) go
    before the prompt, for a check that looks at a picture."""
    blocks = [{"type": "text", "text": text} for text in system]
    content = [_image(url) for url in images] + [{"type": "text", "text": prompt}]
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    # Streamed: long answers (breakdowns) can take longer than the SDK allows unstreamed.
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        system=blocks,
        messages=[{"role": "user", "content": content if images else prompt}],
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        output_format=schema,
        betas=[FALLBACK_BETA],
        fallbacks="default",
    ) as stream:
        try:
            response = stream.get_final_message()
        except ValidationError as exc:  # the JSON was cut off (max_tokens) or malformed
            raise ClaudeError(CUT_OFF, _cost_so_far(stream)) from exc
    cost = _cost(response.usage)
    if response.stop_reason == "refusal":
        category = response.stop_details.category if response.stop_details else None
        raise ClaudeError(f"Claude declined this request ({category or 'no category'}).", cost)
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise ClaudeError(CUT_OFF, cost)
    return Answer(response.parsed_output, response.model, cost)


def _image(url: str) -> dict:
    """A data URL ("data:image/png;base64,…") as an image block."""
    head, data = url.split(",", 1)
    media = head.removeprefix("data:").split(";")[0]
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}


def _cost_so_far(stream) -> Decimal | None:
    try:
        return _cost(stream.current_message_snapshot.usage)
    except AssertionError:  # nothing received yet
        return None


def _cost(usage) -> Decimal:
    tokens = {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "cache_read": usage.cache_read_input_tokens or 0,
        "cache_write": usage.cache_creation_input_tokens or 0,
    }
    return sum((Decimal(n) * PRICE_PER_MTOK[k] / 1_000_000 for k, n in tokens.items()), Decimal(0))
