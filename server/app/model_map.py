"""Reed's model map (4 Nov, changed 6 Nov): which model makes what, and what each needs sent.
Each style has its own video model (Reed, 6 Nov: "keep seedance for the animated and
expression-full ones for now. Omni is more for the realistic stuff"; "1.2 replaces 1.1"): Seedance
2.5 for House and Disney Pixar (and songs), Seedance 2.0 for Skeleton, Claymation, Zack D and Dr.
Pickle, and Gemini Omni 1.2 for the realistic one, UGC. In UGC, how the presenter appears
(host.how) decides the talker: one who stays in one spot the whole time (talks, or in a corner) is
one HeyGen Avatar IV take from a still, lip-synced to our own voice track (a talker's is the
MiniMax voice), and Omni 1.2 makes only the B-roll around them; one who moves around in the story
(acts) has no take of their own, so their shots are made on Omni 1.2 like the B-roll. Every UGC
clip that isn't the HeyGen talker stays on Omni 1.2 (`choose`). Omni always makes its own sound and
takes no audio: in a shot where no one speaks its prompt says so, and a narrated video keeps its
narration throughout (Reed, 5 Nov). The Clips tab shows each clip's model and why (`why`).
Photoreal Seedance B-roll (rule 10's exception, Reed, 4 Nov; now only when a UGC video's model
is switched to Seedance) describes the person from their approved character description, in the
same words in every prompt (clip_takes._in_words), instead of attaching their photo or an opening
still with them in it; products and screens stay attached. Why: in th-20s
(.context/tests/th-20s/REPORT.md) every Seedance 2.0 take sent a photoreal teenager's photo was
refused ("sensitive", E005) and 1 Lite refused it as invalid input (E006), not charged. HeyGen,
Omni and stylised characters keep their references."""

import re

from app import looks

PHOTOREAL = ("ugc",)  # styles whose people are photoreal (a real person filmed on a phone)


def unsent(look: str | None, model_id: str, shots: list[dict]) -> tuple[str, ...]:
    """The references a take leaves out and describes in words instead: in a photoreal style
    on Seedance, every character sheet, and the opening still when someone is in it."""
    if not model_id.startswith("seedance") or looks.base(look or looks.DEFAULT) not in PHOTOREAL:
        return ()
    people = any(s.get("character_ids") for s in shots)
    return ("char:", "frame:") if people else ("char:",)


# --- The model each clip is made with, and why (v6 F: the Clips tab's "Model" and "Why") -------

OMNI = "gemini-omni-1.2"
NOT_VIDEO = "Refused: there's no video model called {}."
WHOLE_TAKE = "Refused: HeyGen makes the talker's one take, not a clip. Use make_take for B-roll."
SAYS_IT = (
    "Refused: this clip is the talker saying the narration to the lens in one spot, cut "
    "from their one HeyGen take in our own voice (Reed, 6 Nov): it stays on HeyGen."
)
REAL = ("Refused: in UGC every clip that isn't the HeyGen talker is made on Omni 1.2, the B-roll "
        "and a talker who moves around in the story (Reed, 6 Nov: \"Omni is more for the "
        "realistic stuff\").")  # fmt: skip
PERSONS = "Refused: {who} chose {model} for this video's clips themselves; their choice stays."
SUNG = "Refused: this clip's shots are sung, so it needs a model that lip-syncs to the song."
SHAPE = "Refused: {model} makes {shapes} videos only; this one is {shape}."
LONG = "Refused: this clip is {seconds} s and {model} makes about {most} s at most."
# Omni has no sound switch (docs/prompting/omni-1.2.md §5)
SILENT = (
    "Sound: no one speaks in this shot (no voices, narration or dialogue), only the sounds "
    "of the place. No music."
)
IMAGE = re.compile(r"\[Image(\d+)\]")
ORDINAL = ("first", "second", "third", "fourth", "fifth", "sixth")


def _model(model_id: str):
    from app.catalogue import get_model

    return get_model(model_id)


def of_clip(project, clip):
    """The clip's model: its own (the director's choice, with its reason) when it has one,
    else the video's (its style's: Omni 1.2 in UGC, Seedance in the animated styles)."""
    from app.breakdown import video_model

    own = _model((clip.model or {}).get("id", "")) if clip is not None else None
    return own or video_model(project)


def own_name(clip) -> str | None:
    """The name of the model the director chose for this clip, if any (no queries)."""
    own = _model((clip.model or {}).get("id", ""))
    return own.name if own else None


def resolution(model) -> str:
    return model.take_resolution


def why(db, project, clip) -> dict:
    """{id, name, why, by} for the Clips tab: the model the clip is made with, in one line."""
    from app import guides, talker
    from app.breakdown import video_model
    from app.narration import video_kind

    if talker.says(db, project, clip):
        found = _model(talker.MODEL)
        return {"id": found.id, "name": found.name, "by": "map",
                "why": "The talker saying the narration: cut from their one HeyGen take, "
                       "lip-synced to the video's own voice."}  # fmt: skip
    if own := clip.model:
        found = _model(own["id"])
        return {"id": found.id, "name": found.name, "why": own.get("why", ""), "by": own["by"]}
    found = video_model(project)
    picked = project.video_model == found.id
    style = guides.style(project.look or looks.DEFAULT)["name"]
    switched = [e for e in project.settings_log or [] if e["field"] == "video_model"]
    by = switched[-1]["by"] if picked and switched else "person"
    if picked and by == "director":
        said = switched[-1].get("why") or "The director chose it for this video."
    elif picked:
        said = "Chosen in this video's settings."
    elif video_kind(db, project) == "song":
        said = f"A song video: {found.name} lip-syncs the sung shots."
    else:
        said = f"{style}'s default for its clips."
    if not found.lip_sync and video_kind(db, project) == "narrated":
        said += (" No one speaks on it: the place's own sound under the narration."
                 if found.audio == "always" else
                 " Silent: B-roll gets sound effects only where they help.")  # fmt: skip
    return {"id": found.id, "name": found.name, "why": said, "by": by if picked else "map"}


def state(db, project, clip) -> dict:
    """What the director reads of a clip's model: its name."""
    return {"model": why(db, project, clip)["name"]}


def _persons(db, project) -> str:
    """Who chose the video's model themselves (settings_move.persons), or ""."""
    from app.auth import user_name
    from app.settings_move import persons

    found = persons(project, "video_model")
    return (user_name(db, found.get("by_id")) or "A person") if found else ""


def choose(db, project, clip, model_id: str | None, reason: str) -> str:
    """The director's model for one clip (null: back to the video's), checked against the
    model map, with its new price said first and its reason shown. It never changes the video's
    own model. A talker in one spot stays on HeyGen and the rest of UGC on Omni 1.2 (Reed,
    6 Nov); in an animated style Omni may make a realistic shot."""
    from app import talker
    from app.clip_takes import take_credits

    was = of_clip(project, clip)
    if model_id is None:
        clip.model = None
        now = of_clip(project, clip).name
        return f"Clip {clip.clip_id.removeprefix('c')} is back on the video's {now}."
    found = _model(model_id)
    if found is None or found.kind != "video":
        return NOT_VIDEO.format(model_id)
    if found.id == talker.MODEL:
        return WHOLE_TAKE
    if talker.says(db, project, clip):
        return SAYS_IT
    if who := _persons(db, project):
        return PERSONS.format(who=who, model=_model(project.video_model).name)
    if found.id != OMNI and looks.base(looks.drawn(project)) in PHOTOREAL:
        return REAL
    if (clip.song_slice or {}).get("sung_shots") and not found.lip_sync:
        return SUNG
    if project.aspect_ratio not in found.aspect_ratios:
        return SHAPE.format(model=found.name, shapes=" or ".join(found.aspect_ratios),
                            shape=project.aspect_ratio)  # fmt: skip
    most = found.duration.max
    if clip.seconds > most:
        return LONG.format(seconds=clip.seconds, model=found.name, most=most)
    then = take_credits(db, project, clip)  # a take's whole price, its check included
    clip.model = {"id": found.id, "why": reason.strip()[:300], "by": "director"}
    now = take_credits(db, project, clip)
    return (
        f"Clip {clip.clip_id.removeprefix('c')} is made on {found.name} now: up to "
        f"{now:.1f} credits a take (was {then:.1f} on {was.name}). Why: {reason.strip()}"
    )


def fit(model, input: dict, files: dict) -> tuple[dict, dict]:
    """A take's input as Omni reads it (docs/prompting/omni-1.2.md): prompt, duration (3–15 s),
    resolution, shape and up to 6 reference pictures; no sound switch, so a take with no one
    speaking says so in words (a narrated video keeps its narration throughout, Reed, 5 Nov).
    Its references are named in words by their order, never as tags like [Image1] (§2, §6);
    the clip prompt's opening still is a reference, never a literal first frame (§1)."""
    if model.id != OMNI:
        return input, files
    pictures = files.get("reference_images", [])[: model.max_reference_images]
    prompt = IMAGE.sub(lambda m: _picture(int(m.group(1)), len(pictures)), input["prompt"])
    if not input.get("generate_audio"):
        prompt = f"{prompt}\n{SILENT}"
    shaped = {"prompt": prompt, "duration": max(model.duration.min, min(input["duration"],
              model.duration.max)), "resolution": resolution(model),
              "aspect_ratio": input["aspect_ratio"]}  # fmt: skip
    return shaped, {"reference_images": pictures} if pictures else {}


def _picture(n: int, sent: int) -> str:
    """[Image2] → "the second reference picture" (one past the six sent: "a picture")."""
    return f"the {ORDINAL[n - 1]} reference picture" if 0 < n <= min(sent, 6) else "a picture"
