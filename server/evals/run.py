"""Run the eval cases through Claude and save each answer for `score.py`. PAID: one run is
12 calls (about $2). Only with the Producer's go-ahead, logged in ops/SPEND.md.

Usage (from server/): python -m evals.run <out dir> [--cap-usd 2] [--cases id ...] [--print]
Key from STUDIO_ANTHROPIC_KEY. Stops before the next call once the cap is reached.
--print is free: it writes each first-round prompt to <case>.<step>.prompt.txt and calls nothing.
Reel import cases start with Gemini's watch, which runs on Replicate with the reel's video
(not from here): put its answer at <out>/<case>.reel_watch.json, then the Claude steps run."""

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

from app.catalogue import get_model
from app.claude import ask, make_client
from app.prompts import (
    SCHEMAS,
    brand_block,
    cast_slots_input,
    number_lines,
    reel_watch_input,
    reference_block,
    schemas,
    system,
    variations_input,
    watch_breakdown,
    watch_system,
)
from evals.score import CASES, reel_inputs

# Room for long scripts (claude.ask streams, so this can exceed the unstreamed limit).
LONG_MAX_TOKENS = 32000


# How the server marks an accepted suggestion in the working script (Designer's spec #69).
TAGS = {
    "camera": "Camera",
    "action": "Movement",
    "reaction": "Reaction",
    "brand_screen": "Brand screen",
}


def apply_all(script: str, suggestions) -> str:
    """Accept every suggestion (what an editor clicking 'Accept all' gets)."""
    lines = script.splitlines()
    before, after = {}, {}
    for s in suggestions:
        n = s.anchor.line
        if not 1 <= n <= len(lines) or s.anchor.quote not in lines[n - 1]:
            continue
        line = f"[{TAGS[s.kind]}] {s.text}"
        (before if s.placement == "before" else after).setdefault(n, []).append(line)
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
        f"{m.max_reference_images} reference images (prefer 8 or fewer), "
        f"{m.max_reference_audios} audios</video_model>"
    )


def run_case(
    client, case: dict, out: Path, spent: list[Decimal], cap: Decimal, dry: bool = False
) -> None:
    brand = CASES["brands"][case["brand"]]
    brand_text = brand_block(brand["brand"], brand["screens"], brand.get("product"))
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
        if not dry and sum(spent) >= cap:
            sys.exit(f"Stopped: spent ${sum(spent):.2f}, cap ${cap}.")
        if step == "reel_watch":  # Gemini, on Replicate with the reel's video: not run from here
            transcript, cuts = reel_inputs(case)
            saved = out / f"{case['id']}.reel_watch.json"
            if dry and cuts:
                text = f"=== SYSTEM\n{watch_system()}\n\n=== USER\n"
                text += (
                    f"[the reel's video and contact sheet]\n{reel_watch_input(transcript, cuts)}\n"
                )
                (out / f"{case['id']}.reel_watch.prompt.txt").write_text(text)
                print(f"{case['id']}.reel_watch: prompt written (free)", flush=True)
            if dry and not cuts:
                print(f"{case['id']}.reel_watch: needs the cut list from prep", flush=True)
            if dry or not saved.exists():  # the later steps need Gemini's answer
                print(
                    f"{case['id']}: the next steps need {saved.name} from a Gemini run", flush=True
                )
                return
            watch = schemas.ReelWatch.model_validate_json(saved.read_text())
            reference = "\n" + reference_block(watch_breakdown(watch, transcript, cuts or []))
            continue
        if step == "enhance":
            prompt = f"{brief}\n{cast}\n<script>\n{number_lines(script)}\n</script>"
        elif step == "script_draft":
            prompt = f"{brief}\n{cast}{reference}"
            if case.get("new_lines"):
                prompt += "\n<new_lines>true</new_lines>"
        elif step == "variations":
            prompt = variations_input(script, case["cast"], case["count"], reference.strip())
        elif step == "cast_slots":
            if dry:  # needs the variations' answer
                return
            made = answers["variations"].variations if "variations" in answers else []
            given = [v.script for v in made] or ["\n".join(v) for v in case.get("versions", [])]
            versions = {0: script} | dict(enumerate(given, 1))
            prompt = cast_slots_input(versions, reference.strip(), case["cast"], case["brief"])
        elif step == "breakdown":
            (out / f"{case['id']}.script.txt").write_text(script)
            prompt = f"{brief}\n{cast}\n{places}\n{video_model()}{reference}\n"
            prompt += f"<script>\n{number_lines(script)}\n</script>"
        else:  # clip_prompts
            if dry:  # needs the breakdown's answer
                return
            bd = answers["breakdown"]
            screens = [
                f'screen:{s["id"]} {brand["brand"]["name"]} "{s["name"]}"' for s in brand["screens"]
            ]  # noqa: E501
            if p := brand.get("product"):
                screens.append(f'product:{p["id"]} {brand["brand"]["name"]} product "{p["name"]}"')
            frames = [f"frame:{c.id} storyboard frame for clip {c.id}" for c in bd.clips]
            assets = case["cast"] + case["places"] + screens + frames
            prompt = f"{video_model()}\n<assets>\n" + "\n".join(assets) + "\n</assets>\n"
            prompt += f"<breakdown>\n{bd.model_dump_json()}\n</breakdown>"
        if dry:
            text = f"=== SYSTEM\n{system(step)}\n\n{brand_text}\n\n=== USER\n{prompt}\n"
            (out / f"{case['id']}.{step}.prompt.txt").write_text(text)
            print(f"{case['id']}.{step}: prompt written (free)", flush=True)
            continue
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
    parser.add_argument("--print", action="store_true", help="write prompts only; no calls")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    client = None if args.print else make_client(os.environ.get("STUDIO_ANTHROPIC_KEY", ""))
    spent: list[Decimal] = []
    for case in CASES["cases"]:
        if args.cases and case["id"] not in args.cases:
            continue
        try:
            run_case(client, case, args.out, spent, args.cap_usd, args.print)
        except Exception as exc:  # noqa: BLE001 - keep going; a failed case is a result
            print(f"{case['id']}: FAILED {exc}", flush=True)
    total = sum(spent)
    (args.out / "cost.json").write_text(json.dumps({"calls": len(spent), "usd": str(total)}))
    print(f"{len(spent)} calls, ${total:.2f}")


if __name__ == "__main__":
    main()
