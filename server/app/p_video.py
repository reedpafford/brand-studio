"""P-Video (prunaai/p-video) takes. It has its own inputs (replicate.com/prunaai/p-video/api):
one `image` (the opening frame), one `audio` (it lip-syncs to it), `fps`, `prompt_upsampling`;
no reference lists, no `generate_audio`. `fit` turns a Seedance-shaped take into one P-Video
reads, and leaves every other model's take alone. Rules from the paid test (presenter-1): 24 fps,
prompt_upsampling off (keep our words), and never the words subtitles, captions or text (even in
"no ...") because they make it draw garbled captions."""

import re

ID, FPS = "p-video", 24
ASKS_FOR_WORDS = re.compile(r"\b(subtitles?|captions?|text)\b", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?])\s+")
CLEAN = "The frame is clean."


def clean(prompt: str) -> str:
    """The prompt without any sentence that says subtitles, captions or text."""
    lines, cut = [], False
    for line in prompt.splitlines():
        sentences = SENTENCE.split(line)
        kept = [s for s in sentences if not ASKS_FOR_WORDS.search(s)]
        cut = cut or len(kept) < len(sentences)
        lines.append(" ".join(kept))
    return "\n".join(x for x in lines if x.strip()) + (f"\n{CLEAN}" if cut else "")


def fit(model_id: str, input: dict, files: dict) -> tuple[dict, dict]:
    """(input, files) as the model reads them: P-Video gets its own keys; a model with no sound
    of its own (Seedance 1 Lite) no `generate_audio` (Replicate refuses a key it doesn't list);
    others the same."""
    from app.catalogue import get_model

    if model_id != ID:
        m = get_model(model_id)
        drop = {"generate_audio"} if m is not None and m.audio is None else set()
        if m is not None and m.fixed_seconds:  # Omni 1.1 lists neither: 10 s clips, with sound
            drop = {"generate_audio", "duration"}
        return {k: v for k, v in input.items() if k not in drop}, files
    shaped = {k: input[k] for k in ("duration", "resolution", "aspect_ratio") if k in input}
    shaped |= {"prompt": clean(input["prompt"]), "fps": FPS, "prompt_upsampling": False}
    own = {"image": (files.get("image") or files.get("reference_images", []))[:1],
           "last_frame_image": files.get("last_frame_image", [])[:1],
           "audio": files.get("reference_audios", [])[:1]}  # fmt: skip
    return shaped, {k: v for k, v in own.items() if v}
