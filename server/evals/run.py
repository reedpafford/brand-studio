"""Run the eval cases through Claude and save each answer for `score.py`. PAID: one run is
12 calls (about $2). Only with the Producer's go-ahead, logged in ops/SPEND.md.

Usage (from server/): python -m evals.run <out dir> [--cap-usd 2] [--cases id ...]
Key from STUDIO_ANTHROPIC_KEY. Stops before the next call once the cap is reached."""

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

from app.catalogue import get_model
from app.claude import ask, make_client
from app.prompts import SCHEMAS, brand_block, number_lines, reference_block, system
from evals.score import CASES

# Room for long scripts; the SDK refuses non-streamed calls above about 21.3k output tokens.
LONG_MAX_TOKENS = 21000


def apply_all(script: str, suggestions) -> str:
    """Accept every suggestion (what an editor clicking 'Accept all' gets)."""
    lines = script.splitlines()
    before, after = {}, {}
    for s in suggestions:
        n = s.anchor.line
        if not 1 <= n <= len(lines) or s.anchor.quote not in lines[n - 1]:
            continue
        (before if s.placement == "before" else after).setdefault(n, []).append(s.text)
    out = []
    for n, line in enumerate(lines, 1):
        out += before.get(n, [])
        out.append(line)
        out += after.get(n, [])
    return "\n".join(out)


def video_model() -> str:
    m = get_model("seedance-2.5")
    return (
        f"<video_model>{m.name}: {m.duration.min}–{m.duration.max} s per clip, up to "
        f"{m.max_reference_images} reference images, {m.max_reference_audios} audios; 9:16, 480p"
        "</video_model>"
    )


def run_case(client, case: dict, out: Path, spent: list[Decimal], cap: Decimal) -> None:
    brand = CASES["brands"][case["brand"]]
    brand_text = brand_block(brand["brand"], brand["screens"])
    cast = "<cast>\n" + "\n".join(case["cast"]) + "\n</cast>"
    places = "<places>\n" + "\n".join(case["places"]) + "\n</places>"
    brief = f"<brief>{case['brief']}</brief>"
    script = "\n".join(case["script"] or [])
    reference = ""
    if ref := case.get("reference"):
        path = Path(__file__).parents[2] / ref["path"]
        reference = "\n" + reference_block(json.loads(path.read_text()), ref["replace"])
    answers = {}
    for step in case["steps"]:
        if sum(spent) >= cap:
            sys.exit(f"Stopped: spent ${sum(spent):.2f}, cap ${cap}.")
        if step == "enhance":
            prompt = f"{brief}\n{cast}\n<script>\n{number_lines(script)}\n</script>"
        elif step == "script_draft":
            prompt = f"{brief}\n{cast}{reference}"
        elif step == "breakdown":
            (out / f"{case['id']}.script.txt").write_text(script)
            prompt = f"{brief}\n{cast}\n{places}\n{video_model()}{reference}\n"
            prompt += f"<script>\n{number_lines(script)}\n</script>"
        else:  # clip_prompts
            bd = answers["breakdown"]
            screens = [
                f'screen:{s["id"]} {brand["brand"]["name"]} "{s["name"]}"' for s in brand["screens"]
            ]  # noqa: E501
            frames = [f"frame:{c.id} storyboard frame for clip {c.id}" for c in bd.clips]
            assets = case["cast"] + case["places"] + screens + frames
            prompt = f"{video_model()}\n<assets>\n" + "\n".join(assets) + "\n</assets>\n"
            prompt += f"<breakdown>\n{bd.model_dump_json()}\n</breakdown>"
        answer = ask(
            client,
            system=[system(step), brand_text],
            prompt=prompt,
            schema=SCHEMAS[step],
            max_tokens=LONG_MAX_TOKENS if step in ("breakdown", "clip_prompts") else 16000,
        )
        spent.append(answer.cost_usd)
        answers[step] = answer.parsed
        (out / f"{case['id']}.{step}.json").write_text(answer.parsed.model_dump_json(indent=1))
        print(f"{case['id']}.{step}: ${answer.cost_usd:.3f} ({answer.model})", flush=True)
        if step == "enhance":
            script = apply_all(script, answer.parsed.suggestions)
        elif step == "script_draft":
            script = answer.parsed.drafts[0].script


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--cap-usd", type=Decimal, default=Decimal(2))
    parser.add_argument("--cases", nargs="*", help="only these case ids (default: all)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    client = make_client(os.environ.get("STUDIO_ANTHROPIC_KEY", ""))
    spent: list[Decimal] = []
    for case in CASES["cases"]:
        if args.cases and case["id"] not in args.cases:
            continue
        try:
            run_case(client, case, args.out, spent, args.cap_usd)
        except Exception as exc:  # noqa: BLE001 - keep going; a failed case is a result
            print(f"{case['id']}: FAILED {exc}", flush=True)
    total = sum(spent)
    (args.out / "cost.json").write_text(json.dumps({"calls": len(spent), "usd": str(total)}))
    print(f"{len(spent)} calls, ${total:.2f}")


if __name__ == "__main__":
    main()
