"""Seedance 2.5 prompt A/B for FIT rows 3, 9 and 10 (docs/prompting/FIT.md). PAID: two 10 s
clips at 480p, about $2.06. Only with the Producer's go-ahead, logged in ops/SPEND.md.

Usage (from server/): python -m evals.seedance_ab <out dir> [--cap-usd 2.20] [--dry-run]
Calls https://api.replicate.com/v1; the sandbox proxy adds the token (or REPLICATE_API_TOKEN).

Same scene, references, seed, settings and audio line in both. Only the rows under test differ:
- A, current style: decimal shot times, "[Image1] storyboard frame, match its look and framing".
- B, new style: whole-second shots with quick cuts sharing a second (row 3), "[Image1] is the
  first frame." (row 9), and Summary and Keep lines (row 10).
Clips run one after the other. Before each submit, what's spent plus that clip's estimate must
fit under the cap, and a clip is never submitted twice. Writes A.mp4, B.mp4, A.json, B.json."""

import argparse
import base64
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

from app.catalogue import get_model
from app.providers import NetworkError, Provider

MODEL = get_model("seedance-2.5")
SETTINGS = {
    "duration": 10,
    "resolution": "480p",
    "aspect_ratio": "9:16",
    "generate_audio": True,
    "seed": 7,
}
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "brands" / "fomo"
IMAGES = [ASSETS / "screens" / "token-up.png", ASSETS / "style-board.png"]

AUDIO = (
    "Audio: only the spoken lines and quiet late-night bedroom room tone. No music, "
    "background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, "
    "swelling tone or stinger. No subtitles."
)
STYLE = "Style: stylized 3D animated feature film, expressive faces."
SETTING = (
    "Setting: Aiden's bedroom at night: dark blue walls, a desk lit by a laptop's cold "
    "glow, warm fairy lights, Jay sprawled on a beanbag by the door. Aiden is 19, messy "
    "black hair, grey hoodie. Jay is 20, curly red hair, green t-shirt."
)
SCREEN = (
    "The phone fills the frame, held still and flat-on, and shows [Image1] exactly: same "
    "layout, numbers, colours and logo, nothing added or changed"
)

A = "\n".join(
    [
        AUDIO,
        'References: [Image1] storyboard frame, match its look and framing; it is the fomo "Token '
        'chart up" screen. [Image2] is the fomo style board; match its look.',
        STYLE,
        SETTING,
        "Shots (hard cuts):",
        f"1. 0.0–1.5 s. Close-up on the phone, static. {SCREEN}.",
        "2. 1.5–2.2 s. Extreme close-up. Aiden's eyes snap wide, mouth falls open.",
        "3. 2.2–2.8 s. Medium close-up. Jay looks up from his phone, one brow raised.",
        "4. 2.8–5.3 s. Low-angle medium shot, push in. Aiden leaps up from the desk chair, "
        "fists in the air. Aiden (yelling): \"It's up. It's actually up!\"",
        "5. 5.3–7.3 s. Medium close-up, static. Jay leans back on the beanbag, unimpressed. "
        'Jay (deadpan): "You said that yesterday."',
        "6. 7.3–10.0 s. Two-shot, slow push in. Aiden turns the phone toward Jay; "
        "it shows [Image1] "
        'exactly. Aiden (calm, grinning): "Yesterday I was early." Jay keeps his mouth closed, his '
        "jaw dropping.",
        AUDIO,
    ]
)

B = "\n".join(
    [
        AUDIO,
        'References: [Image1] is the first frame. It is the fomo "Token chart up" screen. [Image2] '
        "is the fomo style board; match its look.",
        "Summary: Aiden's fomo trade finally pays off in his bedroom at night, and he turns his "
        "doubting roommate Jay's words back on him.",
        STYLE,
        SETTING,
        "Shots (hard cuts):",
        f"Shot 1 | 0–2 s. Close-up on the phone, static. {SCREEN}.",
        "Shot 2 | 2–3 s. Two quick cuts: an extreme close-up of Aiden, his eyes snap wide and his "
        "mouth falls open; then a medium close-up of Jay looking up from his phone, "
        "one brow raised.",
        "Shot 3 | 3–5 s. Low-angle medium shot, push in. Aiden leaps up from the desk chair, "
        "fists in the air. Aiden (yelling): \"It's up. It's actually up!\"",
        "Shot 4 | 5–7 s. Medium close-up, static. Jay leans back on the beanbag, unimpressed. "
        'Jay (deadpan): "You said that yesterday."',
        "Shot 5 | 7–10 s. Two-shot, slow push in. Aiden turns the phone toward Jay; "
        "it shows [Image1] "
        'exactly. Aiden (calm, grinning): "Yesterday I was early." Jay keeps his mouth closed, his '
        "jaw dropping.",
        "Keep: Aiden and Jay as described, one of each; the phone screen exactly as [Image1].",
        AUDIO,
    ]
)

VARIANTS = {"A": A, "B": B}


def estimate() -> Decimal:
    return SETTINGS["duration"] * MODEL.usd_per_unit(SETTINGS["resolution"])


def job_input(prompt: str) -> dict:
    images = [f"data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}" for p in IMAGES]
    return {"model": MODEL.id, "input": {**SETTINGS, "prompt": prompt, "reference_images": images}}


def run(
    out: Path, provider: Provider, cap: Decimal, poll_every: float = 10, timeout: float = 1200
) -> Decimal:
    """Run A then B. Returns the total spent; stops before anything that could pass `cap`."""
    out.mkdir(parents=True, exist_ok=True)
    spent = Decimal(0)
    for name, prompt in VARIANTS.items():
        if spent + estimate() > cap:
            print(f"Stopping before {name}: ${spent} spent + ${estimate()} would pass ${cap}.")
            break
        ref = provider.submit("video", job_input(prompt))  # never retried: it costs money
        print(f"{name}: started {ref}")
        started, result = time.monotonic(), None
        while time.monotonic() - started < timeout:
            try:
                result = provider.poll(ref)
            except NetworkError as exc:
                print(f"{name}: check failed ({exc}); trying again")
            if result and result.state != "running":
                break
            time.sleep(poll_every)
        if not result or result.state == "running":
            print(
                f"{name}: still running after {timeout:.0f} s; check {ref} on Replicate. Stopping."
            )
            spent += estimate()  # assume it will be billed
            break
        cost = sum((u.cost_usd for u in result.usage), Decimal(0))
        spent += cost if result.usage else estimate()
        usage = [
            vars(u) | {"units": str(u.units), "cost_usd": str(u.cost_usd)} for u in result.usage
        ]
        (out / f"{name}.json").write_text(
            json.dumps(
                {
                    "prediction": ref,
                    "state": result.state,
                    "error": result.error,
                    "usage": usage,
                    "settings": SETTINGS,
                    "prompt": prompt,
                },
                indent=1,
            )
        )
        for url in result.files[:1]:
            data, _ = provider.fetch(url)
            (out / f"{name}.mp4").write_bytes(data)
        print(f"{name}: {result.state}, ${cost} {usage or '(no usage reported)'}")
        if spent > cap:
            print(f"Spent ${spent}, over the ${cap} cap. Stopping.")
            break
    print(f"Total spent: ${spent} (cap ${cap}). Log it in ops/SPEND.md.")
    return spent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--cap-usd", type=Decimal, default=Decimal("2.20"))
    parser.add_argument("--dry-run", action="store_true", help="print prompts and cost; no calls")
    args = parser.parse_args()
    if args.dry_run:
        for name, prompt in VARIANTS.items():
            print(f"--- {name} ---\n{prompt}\n")
        print(f"Settings: {SETTINGS}; images: {[p.name for p in IMAGES]}")
        print(f"Estimate: 2 x ${estimate()} = ${2 * estimate()} (cap ${args.cap_usd})")
        return
    from app.providers.replicate import ReplicateProvider

    provider = ReplicateProvider(
        "https://api.replicate.com/v1", token=os.environ.get("REPLICATE_API_TOKEN", "")
    )
    sys.exit(0 if run(args.out, provider, args.cap_usd) <= args.cap_usd else 1)


if __name__ == "__main__":
    main()
