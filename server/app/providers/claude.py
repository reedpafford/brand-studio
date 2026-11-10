"""Claude as a job provider. Answers come back in the same call, so the worker runs it with
`run()` instead of submit/poll. Failed calls aren't billed by Anthropic, so "busy" and server
errors are safe to retry; a dropped connection is treated as "unsure", like other paid work."""

import json
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import anthropic

from app.claude import ClaudeError, ask, make_client
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
# Steps whose parts, written in order, are joined by renumbering each onto the last
BREAKDOWNS = ("breakdown", "song_breakdown", "narrated_breakdown")


def join(output: dict, answer: dict) -> dict:
    """One part's answer added to the run's: lists joined in part order, a yes/no only when
    every part says yes (a stills review's `ready`), anything else as the first part said it."""
    out = dict(output)
    for key, value in answer.items():
        if isinstance(value, list):
            out[key] = out.get(key, []) + value
        elif isinstance(value, bool):
            out[key] = out.get(key, True) and value
        else:
            out.setdefault(key, value)
    return out


def in_order(input: dict, ask: Callable[[str, list[str]], object]) -> Result:
    """`parts` written one after another ("in_order": a long video's shots and stills, so it
    is still thought of as a whole, Reed 10 Nov): each part reads the shared prompt and every
    earlier part's answer (`ask(part, before)`), and its answer joins the run's in order (a
    breakdown's renumbered to carry on from the one before: breakdown.continued). A part that
    fails is asked once more, alone; failing again fails the job, with what was spent. Busy
    or lost before anything was billed: raised, for the worker's usual rules."""
    from app.enhance import escape

    output, before, cost, tokens = {}, [], Decimal(0), {}
    for i, part in enumerate(input["parts"]):
        answer = error = None
        for _ in range(2):
            try:
                answer = ask(part, before)
                break
            except (ClaudeError, NotStarted, NetworkError) as exc:
                error, cost = exc, cost + (getattr(exc, "cost_usd", None) or 0)
        if answer is None:
            if not cost and not isinstance(error, ClaudeError):
                raise error
            usage = [UsageItem(Decimal(1), "call", cost, tokens=tokens or None)] if cost else []
            return Result("failed", error=str(error), usage=usage)
        cost += answer.cost_usd
        for key, n in (getattr(answer, "tokens", None) or {}).items():
            tokens[key] = tokens.get(key, 0) + n
        found = clean(answer.parsed.model_dump())
        if input["step"] in BREAKDOWNS:  # renumbered on; a scene carried on is one scene
            from app.breakdown import continued

            output, piece = continued(output, found, i in input.get("carry_on", []))
        else:
            output, piece = join(output, found), found
        before.append(f'<written part="{i + 1}">\n{escape(json.dumps(piece, ensure_ascii=False))}'
                      "\n</written>")  # fmt: skip
    usage = [UsageItem(Decimal(1), "call", cost, tokens=tokens or None)] if cost else []
    return Result("succeeded", output=output, usage=usage)


class ClaudeProvider:
    name = "claude"
    paid = True
    sync = True

    def __init__(self, key: str, client: anthropic.Anthropic | None = None):
        self._key, self._client = key, client

    def run(self, kind: str, input: dict) -> Result:
        """`input`: {"step", "system": [parts], "prompt", "effort"?, "max_tokens"?}, and for a
        check that looks at pictures, "files": {"reference_images": [file ids]}, sent as data
        URLs. With "parts" (e.g. clip prompts, one clip each), each part is asked on its
        own after the shared prompt, so no answer runs out of room: the first goes alone until its
        answer begins (by then it has written the shared prompt's cache: a cache is readable
        once its answer starts streaming), then the rest, up to PARALLEL at once, read it (each
        sees only the shared prompt, never another part's answer), and their lists are
        joined in part order; a part that fails is listed in "failed_parts" ({part, error}) and
        the rest are kept. All of them failing fails the job. "part_images" (one list a part,
        of places in its reference_images) sends each part only its own pictures (a long
        video's stills review, a batch of stills a part). "in_order": see `in_order`."""
        if input.get("in_order") and input.get("parts"):
            return in_order(input, lambda part, before: self._ask(
                input, part, shared=input["prompt"], before=before))  # fmt: skip
        parts = input.get("parts") or [""]
        begun = threading.Event()
        pictures = (input.get("input") or {}).get("reference_images", [])
        own = input.get("part_images")

        def one(i: int, part: str, first: bool = False):
            seen = {"images": [pictures[k] for k in own[i]]} if own else {}
            try:
                if not part:
                    return self._ask(input, input["prompt"])
                return self._ask(input, part, shared=input["prompt"],
                                 started=begun.set if first else None, **seen)  # fmt: skip
            except (ClaudeError, NotStarted, NetworkError) as exc:
                return exc
            finally:
                begun.set()  # never leave the rest waiting on a part that failed early

        with ThreadPoolExecutor(max_workers=min(PARALLEL, len(parts))) as pool:
            first = pool.submit(one, 0, parts[0], True)
            begun.wait()  # its answer has begun: the shared prompt is cached for the rest
            rest = [pool.submit(one, i, part) for i, part in enumerate(parts[1:], 1)]
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
                output = join(output, clean(answer.parsed.model_dump()))
        if len(unasked) == len(parts):  # nothing answered or billed: the worker's usual rules
            raise next((e for e in unasked if isinstance(e, NetworkError)), unasked[0])
        usage = [UsageItem(Decimal(1), "call", cost, tokens=tokens or None)] if cost else []
        if len(failed) == len(parts):
            return Result("failed", error="; ".join(f["error"] for f in failed), usage=usage)
        if failed:
            output["failed_parts"] = failed
        return Result("succeeded", output=output, usage=usage)

    def _ask(self, input: dict, prompt: str, shared: str = "", started=None, images=None,
             before=()):  # fmt: skip
        if not self._key:
            raise NoKey("Claude")
        client = self._client or make_client(self._key)
        if images is None:
            images = (input.get("input") or {}).get("reference_images", [])
        try:
            return ask(
                client,
                system=input["system"],
                prompt=prompt,
                schema=SCHEMAS[input["step"]],
                effort=input.get("effort", "high"),
                images=images,
                shared=shared,
                before=before,
                cache_ttl=LONG_CACHE.get(input["step"], "5m"),
                started=started,
                strict=input["step"] not in LOOSE,
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
