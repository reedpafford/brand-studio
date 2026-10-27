"""Claude as a job provider. Answers come back in the same call, so the worker runs it with
`run()` instead of submit/poll. Failed calls aren't billed by Anthropic, so "busy" and server
errors are safe to retry; a dropped connection is treated as "unsure", like other paid work."""

import re
from decimal import Decimal

import anthropic

from app.claude import ClaudeError, ask, make_client
from app.prompts import SCHEMAS
from app.providers import NetworkError, NotStarted, Result, UsageItem

CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # all but tab, newline, return


def clean(value):
    """Stray control characters out of every string in an answer (NUL, escape, …). Tabs,
    newlines and returns stay, so a tabbed script's quotes still match; nothing else changes."""
    if isinstance(value, str):
        return CONTROL.sub("", value)
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


class ClaudeProvider:
    name = "claude"
    paid = True
    sync = True

    def __init__(self, key: str, client: anthropic.Anthropic | None = None):
        self._key, self._client = key, client

    def run(self, kind: str, input: dict) -> Result:
        """`input`: {"step", "system": [parts], "prompt", "effort"?, "max_tokens"?}, and for a
        check that looks at pictures, "files": {"reference_images": [file ids]}, sent as data
        URLs. With "parts" (e.g. clip prompts, a few clips each), each part is asked on its
        own after the shared prompt, so no answer runs out of room, and their lists are
        joined; a part that fails is listed in "failed_parts" ({part, error}) and the rest
        are kept. All of them failing fails the job."""
        parts = input.get("parts") or [""]
        output: dict = {}
        failed, cost = [], Decimal(0)
        for i, part in enumerate(parts):
            try:
                answer = self._ask(input, f"{input['prompt']}\n{part}" if part else input["prompt"])
            except ClaudeError as exc:  # refused or cut off: still billed, so record the cost
                failed.append({"part": i, "error": str(exc)})
                cost += exc.cost_usd or 0
                continue
            except (NotStarted, NetworkError) as exc:
                if not output and not failed:  # nothing asked yet: the worker's usual rules
                    raise
                failed.append({"part": i, "error": str(exc)})
                continue
            cost += answer.cost_usd
            for key, value in clean(answer.parsed.model_dump()).items():
                output[key] = output.get(key, []) + value if isinstance(value, list) else value
        usage = [UsageItem(Decimal(1), "call", cost)] if cost else []
        if len(failed) == len(parts):
            return Result("failed", error="; ".join(f["error"] for f in failed), usage=usage)
        if failed:
            output["failed_parts"] = failed
        return Result("succeeded", output=output, usage=usage)

    def _ask(self, input: dict, prompt: str):
        client = self._client or make_client(self._key)
        try:
            return ask(
                client,
                system=input["system"],
                prompt=prompt,
                schema=SCHEMAS[input["step"]],
                effort=input.get("effort", "high"),
                images=(input.get("input") or {}).get("reference_images", []),
                **({"max_tokens": input["max_tokens"]} if "max_tokens" in input else {}),
            )
        except (
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            anthropic.OverloadedError,
        ) as exc:
            raise NotStarted(repr(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise NetworkError(repr(exc)) from exc

    def submit(self, kind: str, input: dict) -> str:  # pragma: no cover - sync provider
        raise NotImplementedError

    def poll(self, ref: str) -> Result:  # pragma: no cover - sync provider
        raise NotImplementedError

    def fetch(self, url: str) -> tuple[bytes, str]:  # pragma: no cover - no files
        raise NotImplementedError
