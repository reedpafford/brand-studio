"""Reed's model map (4 Nov): which model makes what, and what each needs sent. A presenter talker
is HeyGen Avatar IV from a still with our MiniMax voice; every other shot, a talker acting in
the story included, is the style's Seedance (2.0 or 2.5, or 1 Lite where enough), silent, with
sound effects added where they help; Omni (Gemini Omni 1.1) only for a talker's shot that needs
what Seedance can't give (`needs`), the reason shown, never B-roll, and the talker never speaks
on it: a narrated video keeps its narration throughout (Reed, 5 Nov). The director picks a
clip's model from the guide and says why (`choose`); the Clips tab shows each clip's model and
why (`why`). Photoreal Seedance B-roll (rule 10's exception, Reed, 4 Nov) describes the person
from their approved character description, in the same words in every prompt
(clip_takes._in_words), instead of attaching their photo or an opening still with them in it;
products and screens stay attached. Why: in th-20s (.context/tests/th-20s/REPORT.md) every
Seedance 2.0 take sent a photoreal teenager's photo was refused ("sensitive", E005) and 1 Lite
refused it as invalid input (E006), not charged. That test doesn't show every photoreal
reference is refused, and words don't guarantee the person looks the same in every shot. HeyGen,
Omni and stylised characters keep their references."""

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

OMNI = "gemini-omni-1.1"
TALKER_RESOLUTION = "720p"  # Omni's talker shots: as real as HeyGen's 720p talker (batch-b)
ONLY_TALKER = ("Refused: Omni makes only a shot of the talker that needs it; never B-roll "
               "(Reed's model map).")  # fmt: skip
# What Omni can do that the style's Seedance can't, in a silent shot (Reed, 5 Nov: "Reserve Omni
# for shots that specifically need its capabilities, with the reason shown"): keep a photoreal
# person's face from their picture, which Seedance refuses (th-20s: E005/E006)
LIKENESS = "likeness"
NOT_NEEDED = ("Refused: the style's Seedance makes this shot (Seedance 1 Lite where it's "
              "enough). Omni is only for a shot that needs what Seedance can't give: in a "
              "photoreal style, the talker's face kept from their picture. Appearing or moving "
              "in a shot isn't a reason by itself.")  # fmt: skip
NO_REASON = ("Refused: say in `why` what this shot needs from Omni that Seedance can't give; "
             "it's shown on the clip.")  # fmt: skip
NO_TALKER = "Refused: this video has no talker, so Omni has nothing to make here."
SAYS_IT = ("Refused: this clip is the talker saying the narration to the lens, cut from their "
           "HeyGen take in our own voice. Omni makes the talker's shots where they act in the "
           "story without speaking: the narration runs throughout.")  # fmt: skip
NOT_VIDEO = "Refused: there's no video model called {}."
UNAPPROVED = ("Refused: Omni makes only shots of the approved plan that need it; approve "
              "the plan first.")  # fmt: skip
WHOLE_TAKE = "Refused: HeyGen makes the talker's one take, not a clip. Use make_take for B-roll."
PERSONS = "Refused: {who} chose {model} for this video's clips themselves; their choice stays."
SUNG = "Refused: this clip's shots are sung, so it needs a model that lip-syncs to the song."
SHAPE = "Refused: {model} makes {shapes} videos only; this one is {shape}."
LONG = "Refused: this clip is {seconds} s and {model} makes about {most} s at most."
SILENT = (
    "Sound: the talker doesn't speak in this shot; no one talks, only the sounds of the place. "
    "No music."
)  # a narrated video keeps its narration throughout (Reed, 5 Nov); its ambient sound stays


def _model(model_id: str):
    from app.catalogue import get_model

    return get_model(model_id)


def of_clip(project, clip):
    """The clip's model: its own (the director's choice, with its reason) when it has one,
    else the video's (its style's Seedance). Nothing defaults to Omni (Reed, 5 Nov)."""
    from app.breakdown import video_model

    own = _model((clip.model or {}).get("id", "")) if clip is not None else None
    return own or video_model(project)


def own_name(clip) -> str | None:
    """The name of the model the director chose for this clip, if any (no queries)."""
    own = _model((clip.model or {}).get("id", ""))
    return own.name if own else None


def seconds(model, clip_seconds: int) -> int:
    """What a take is billed for: a model with no duration input makes its fixed length."""
    return max(model.fixed_seconds, clip_seconds) if model.fixed_seconds else clip_seconds


def resolution(model) -> str:
    return TALKER_RESOLUTION if model.talker_only else model.take_resolution


def _shots(db, clip) -> list[dict]:
    from app.models.breakdowns import BreakdownVersion

    data = (bd.data if (bd := db.get(BreakdownVersion, clip.breakdown_id or 0)) else {}) or {}
    ids = next((c["shot_ids"] for c in data.get("clips", []) if c["id"] == clip.clip_id), [])
    by_id = {s["id"]: s for sc in data.get("scenes", []) for s in sc.get("shots", [])}
    return [by_id[i] for i in ids if i in by_id]


def shows_talker(db, project, clip) -> bool:
    """The clip's shots show the video's talker (its host's cast look)."""
    from app import host

    item = host.host_look(db, project) if host.presents(db, project) else None
    return bool(item) and any(f"char:{item.id}" in (s.get("character_ids") or [])
                              for s in _shots(db, clip))  # fmt: skip


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
        said += " Silent: B-roll gets sound effects only where they help."
    return {"id": found.id, "name": found.name, "why": said, "by": by if picked else "map"}


def state(db, project, clip) -> dict:
    """What the director reads of a clip's model: its name, and whether the talker is in it
    (the only clips Omni may make)."""
    out = {"model": why(db, project, clip)["name"]}
    return {**out, "shows_talker": True} if shows_talker(db, project, clip) else out


def _persons(db, project) -> str:
    """Who chose the video's model themselves (settings_move.persons), or ""."""
    from app.auth import user_name
    from app.settings_move import persons

    found = persons(project, "video_model")
    return (user_name(db, found.get("by_id")) or "A person") if found else ""


def needs(project) -> str | None:
    """What Omni would give this video's talker shots that its Seedance can't, or None: in a
    photoreal style, the talker's face kept from their picture (Seedance refuses it)."""
    return LIKENESS if looks.base(looks.drawn(project)) in PHOTOREAL else None


def expected(db, project, clip) -> bool:
    """The quote prices this clip on Omni (rule 36: never below what it can charge): it has no
    model of its own yet, the presenter acts in the story in a photoreal style and the shot
    shows them, so the director's path for it is Omni. Its model stays the video's until the
    director chooses (`choose`): nothing defaults to Omni."""
    from app import host

    return (not (clip.model or {}).get("id") and host.how(project) == "acts"
            and clip.seconds <= _model(OMNI).fixed_seconds  # longer: Omni can't make it
            and needs(project) == LIKENESS and shows_talker(db, project, clip))  # fmt: skip


def on_omni(db, project, data: dict) -> set[str]:
    """The plan's clips the quote prices on Omni before their rows exist (`expected`)."""
    from app import host

    if host.how(project) != "acts" or needs(project) != LIKENESS or not host.presents(db, project):
        return set()
    item = host.host_look(db, project)
    if item is None:
        return set()
    shots = {s["id"]: s for sc in data.get("scenes", []) for s in sc.get("shots", [])}
    most = _model(OMNI).fixed_seconds  # a longer clip can't be made on Omni
    return {c["id"] for c in data.get("clips", []) if c.get("seconds", 0) <= most
            and any(f"char:{item.id}" in (shots.get(i, {}).get("character_ids") or [])
                    for i in c["shot_ids"])}  # fmt: skip


def omni_take(db, project, clip_seconds: int):
    """One Omni take, as `take_credits` would price it (its fixed length, 720p)."""
    from decimal import Decimal

    from app.credits import estimate

    omni = _model(OMNI)
    job = {"model": omni.id, "input": {"resolution": resolution(omni)}}
    return estimate(db, project.workspace_id, "video", Decimal(seconds(omni, clip_seconds)), job)


def choose(db, project, clip, model_id: str | None, reason: str) -> str:
    """The director's model for one clip (null: back to the video's), checked against the
    model map, with its new price said first. It never changes the video's own model. Omni only
    for a talker's shot that needs what Seedance can't give (`needs`), the reason given and
    shown; on it the talker acts without speaking: a narrated video keeps its narration
    throughout (Reed, 5 Nov)."""
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
    if found.talker_only:
        from app import host, plans

        if not host.presents(db, project):
            return NO_TALKER
        if plans.status(db, project) != "approved":  # Reed: approved acting shots only
            return UNAPPROVED
        if talker.says(db, project, clip):
            return SAYS_IT
        if not shows_talker(db, project, clip):
            return ONLY_TALKER
        if needs(project) != LIKENESS:
            return NOT_NEEDED
        if not reason.strip():
            return NO_REASON
    elif who := _persons(db, project):
        return PERSONS.format(who=who, model=_model(project.video_model).name)
    if (clip.song_slice or {}).get("sung_shots") and not found.lip_sync:
        return SUNG
    if project.aspect_ratio not in found.aspect_ratios:
        return SHAPE.format(model=found.name, shapes=" or ".join(found.aspect_ratios),
                            shape=project.aspect_ratio)  # fmt: skip
    most = found.fixed_seconds or found.duration.max
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
    """A take's input as a talker-only model reads it (Omni: prompt, resolution, shape and its
    reference pictures; no duration, no sound switch, its own sound always). A narrated video
    keeps its narration throughout, so on Omni the talker acts without speaking and its own
    sound (the place, the action) stays under the voice (Reed, 5 Nov)."""
    if not model.talker_only:
        return input, files
    shaped = {"prompt": f"{input['prompt']}\n{SILENT}", "resolution": resolution(model),
              "aspect_ratio": input["aspect_ratio"]}  # fmt: skip
    pictures = files.get("reference_images", [])[: model.max_reference_images]
    return shaped, {"reference_images": pictures} if pictures else {}
