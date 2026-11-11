"""Claude as a job provider. Answers come back in the same call, so the worker runs it with
`run()` instead of submit/poll. Failed calls aren't billed by Anthropic, so "busy" and server
errors are safe to retry; a dropped connection is treated as "unsure", like other paid work."""

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import anthropic

from app.claude import MODEL, ClaudeError, ask, make_client
from app.prompts import SCHEMAS
from app.providers import NetworkError, NoKey, NotStarted, Result, UsageItem

PARALLEL = 8  # parts asked at once: a clip prompt run is one part a clip
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


# Steps whose fixed instructions come back after more than 5 minutes within a run (cost
# analysis, session 35): the director's turns wait on takes and on people, and take watches
# land as takes finish. Their cache lives an hour; every other step keeps the 5-minute one.
LONG_CACHE = {"director": "1h", "take_watch": "1h"}
# Steps sent without constrained decoding (strict structured output): the director's answer
# schema compiles to a grammar Anthropic refuses as too large (jobs 3234-3236, 10 Nov), so its
# answer is checked against the same model on our side instead (`claude.ask`, strict=False).
LOOSE = {"director"}


def model_for(step: str) -> str:
    """The model a step is asked on: the usual one, but for the one-pass director's plan when
    the site sets another (`Settings.one_pass_model`, BS_ONE_PASS_MODEL); no other step."""
    from app.settings import get_settings

    return (get_settings().one_pass_model or MODEL) if step == "one_pass" else MODEL


class ClaudeProvider:
    name = "claude"
    paid = True
    sync = True
    shows_thinking = True  # `run` takes `live`: the call's stream as it comes (app/thinking.py)

    def __init__(self, key: str, client: anthropic.Anthropic | None = None):
        self._key, self._client = key, client

    def run(self, kind: str, input: dict, live=None) -> Result:
        """`input`: {"step", "system": [parts], "prompt", "effort"?, "max_tokens"?}, and for a
        check that looks at pictures, "files": {"reference_images": [file ids]}, sent as data
        URLs. With "parts" (e.g. clip prompts, one clip each), each part is asked on its
        own after the shared prompt, so no answer runs out of room: the first goes alone until its
        answer begins (by then it has written the shared prompt's cache: a cache is readable
        once its answer starts streaming), then the rest, up to PARALLEL at once, read it (each
        sees only the shared prompt, never another part's answer), and their lists are
        joined in part order; a part that fails is listed in "failed_parts" ({part, error}) and
        the rest are kept. All of them failing fails the job."""
        parts = input.get("parts") or [""]
        begun = threading.Event()

        def one(part: str, first: bool = False):
            try:
                if not part:
                    return self._ask(input, input["prompt"], live=live)
                return self._ask(input, part, shared=input["prompt"],
                                 started=begun.set if first else None)  # fmt: skip
            except (ClaudeError, NotStarted, NetworkError) as exc:
                return exc
            finally:
                begun.set()  # never leave the rest waiting on a part that failed early

        with ThreadPoolExecutor(max_workers=min(PARALLEL, len(parts))) as pool:
            first = pool.submit(one, parts[0], True)
            begun.wait()  # its answer has begun: the shared prompt is cached for the rest
            rest = [pool.submit(one, part) for part in parts[1:]]
            answers = [first.result(), *(f.result() for f in rest)]  # in part order
        output: dict = {}
        failed, cost, unasked, tokens = [], Decimal(0), [], {}
        for i, answer in enumerate(answers):
            if isinstance(answer, ClaudeError):  # refused or cut off: still billed
                failed.append({"part": i, "error": str(answer)})
                cost += answer.cost_usd or 0
            elif isinstance(answer, (NotStarted, NetworkError)):
                failed.append({"part": i, "error": str(answer)})
                unasked.append(answer)
            else:
                cost += answer.cost_usd
                for key, n in (getattr(answer, "tokens", None) or {}).items():  # parts summed
                    tokens[key] = tokens.get(key, 0) + n
                for key, value in clean(answer.parsed.model_dump()).items():
                    output[key] = output.get(key, []) + value if isinstance(value, list) else value
        if len(unasked) == len(parts):  # nothing answered or billed: the worker's usual rules
            raise next((e for e in unasked if isinstance(e, NetworkError)), unasked[0])
        usage = [UsageItem(Decimal(1), "call", cost, tokens=tokens or None)] if cost else []
        if len(failed) == len(parts):
            return Result("failed", error="; ".join(f["error"] for f in failed), usage=usage)
        if failed:
            output["failed_parts"] = failed
        return Result("succeeded", output=output, usage=usage)

    def _ask(self, input: dict, prompt: str, shared: str = "", started=None, live=None):
        if not self._key:
            raise NoKey("Claude")
        client = self._client or make_client(self._key)
        try:
            return ask(
                client,
                system=input["system"],
                prompt=prompt,
                schema=SCHEMAS[input["step"]],
                effort=input.get("effort", "high"),
                images=(input.get("input") or {}).get("reference_images", []),
                shared=shared,
                cache_ttl=LONG_CACHE.get(input["step"], "5m"),
                started=started,
                strict=input["step"] not in LOOSE,
                model=model_for(input["step"]),
                live=live,
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
