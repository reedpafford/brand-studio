"""Claude as a job provider. Answers come back in the same call, so the worker runs it with
`run()` instead of submit/poll. Failed calls aren't billed by Anthropic, so "busy" and server
errors are safe to retry; a dropped connection is treated as "unsure", like other paid work."""

from decimal import Decimal

import anthropic

from app.claude import ClaudeError, ask, make_client
from app.prompts import SCHEMAS
from app.providers import NetworkError, NotStarted, Result, UsageItem


class ClaudeProvider:
    name = "claude"
    paid = True
    sync = True

    def __init__(self, key: str, client: anthropic.Anthropic | None = None):
        self._key, self._client = key, client

    def run(self, kind: str, input: dict) -> Result:
        """`input`: {"step", "system": [parts], "prompt", "effort"?}."""
        client = self._client or make_client(self._key)
        try:
            answer = ask(
                client,
                system=input["system"],
                prompt=input["prompt"],
                schema=SCHEMAS[input["step"]],
                effort=input.get("effort", "high"),
            )
        except ClaudeError as exc:
            return Result("failed", error=str(exc))
        except (anthropic.RateLimitError, anthropic.InternalServerError) as exc:
            raise NotStarted(repr(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise NetworkError(repr(exc)) from exc
        return Result(
            "succeeded",
            output=answer.parsed.model_dump(),
            usage=[UsageItem(Decimal(1), "call", answer.cost_usd)],
        )

    def submit(self, kind: str, input: dict) -> str:  # pragma: no cover - sync provider
        raise NotImplementedError

    def poll(self, ref: str) -> Result:  # pragma: no cover - sync provider
        raise NotImplementedError

    def fetch(self, url: str) -> tuple[bytes, str]:  # pragma: no cover - no files
        raise NotImplementedError
