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
NO_REASON = ("Refused: say in `why` what this shot needs from Omni 1.2; it's shown on the clip "
             "(Reed, 6 Nov: \"with its reason shown\").")  # fmt: skip
WHOLE = ("Refused: {style}'s videos are made on {model} (Reed, 6 Nov: \"keep seedance for the "
         "animated and expression-full ones for now. Omni is more for the realistic stuff\"). "
         "Switch the whole video only when a person asks in the chat (name their "
         "note).")  # fmt: skip
PERSONS = "Refused: {who} chose {model} for this video's clips themselves; their choice stays."
SUNG = "Refused: this clip's shots are sung, so it needs a model that lip-syncs to the song."
SHAPE = "Refused: {model} makes {shapes} videos only; this one is {shape}."
LONG = "Refused: this clip is {seconds} s and {model} makes about {most} s at most."
# Omni's prompt words (docs/prompting/omni-1.2.md): no sound switch, so one short sound line
# in place of Seedance's (§5); references named by order (§2, §6), the opening still a guide,
# never "the first frame" (row 3); one shot asked for in words, as it cuts by default (§3)
SILENT = ("Sound: no one speaks in this shot (no voices, narration or dialogue), only {room}. "
          "No music.")  # fmt: skip
SPOKEN = "Sound: only the spoken lines, each from the person who says it, and {room}. No music."
PLACE = "the sounds of the place"
ONE_SHOT = "One continuous shot, no scene cuts."
AUDIO = re.compile(r"^Audio:.*(?:\n|$)", re.M)  # Seedance's audio line, first and last
ROOM = re.compile(r"\bonly (?:the spoken lines and )?(.+?)\. No music", re.I)
FIRST = re.compile(r"\[Image(\d+)\] is the first frame\b")
IMAGE = re.compile(r"\[Image(\d+)\]")
SHOT = re.compile(r"^Shot \d+ \|", re.M)
ORDINAL = ("first", "second", "third", "fourth", "fifth", "sixth")
PEOPLE = 2  # Omni: 2 people a clip, 3 pictures each (§6); each sends one sheet


def _model(model_id: str):
    from app.catalogue import get_model

    return get_model(model_id)


def of_clip(project, clip):
    """The clip's model: its own (the director's choice, with its reason) when it has one,
    else, when someone speaks on camera and the video's Seedance can't lip-sync, its Seedance
    that can (`lip_synced`), else the video's (its style's: Omni 1.2 in UGC, Seedance in the
    animated styles)."""
    from app.breakdown import video_model

    own = _model((clip.model or {}).get("id", "")) if clip is not None else None
    return own or lip_synced(project, clip) or video_model(project)


LIP_SYNCED = ("Someone speaks on camera here and {was} can't lip-sync, so this clip is made "
              "on {now}, which can.")  # fmt: skip


def lip_synced(project, clip):
    """The Seedance that lip-syncs (Seedance 2.5) for a clip where someone speaks on camera,
    when the video's own Seedance can't (Seedance 2.0: Claymation, Skeleton, Zack D offer
    dialogue), or None. Only within Seedance (Reed: the animated styles stay on Seedance), and
    only a line said on camera (`lips_on_camera`: never "(O.S.)", "(ON PHONE)"…). A clip with its
    own model, a video model a person chose, one that lip-syncs or isn't Seedance, or a style
    whose guide says `lip_sync: no`, stays as it is."""
    from sqlalchemy.orm import object_session

    from app import guides
    from app.breakdown import video_model
    from app.catalogue import catalogue
    from app.clip_takes import _shots as shots_of
    from app.clip_takes import lips_on_camera
    from app.models.breakdowns import BreakdownVersion
    from app.settings_move import persons

    m, db = video_model(project), object_session(project)
    if clip is None or clip.model or m.lip_sync or not m.id.startswith("seedance") or db is None:
        return None
    if not guides.style(looks.base(project.look or looks.DEFAULT))["lip_sync"]:
        return None  # the style's guide says its speakers don't lip-sync (`lip_sync: no`)
    bd = db.get(BreakdownVersion, clip.breakdown_id or 0)
    ids = next((c["shot_ids"] for c in (bd.data if bd else {}).get("clips", [])
                if c["id"] == clip.clip_id), [])  # fmt: skip
    shots = shots_of(bd.data, ids) if bd else []
    if persons(project, "video_model") or not lips_on_camera(db, project, clip, shots):
        return None
    return next((x for x in catalogue().values() if x.kind == "video" and x.lip_sync
                 and x.id.startswith("seedance")), None)  # fmt: skip


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
    own = clip.model or {}
    if found := _model(own.get("id", "")):  # one since taken out of the catalogue: the video's
        return {"id": found.id, "name": found.name, "why": own.get("why", ""), "by": own["by"]}
    if spoken := lip_synced(project, clip):
        said = LIP_SYNCED.format(was=video_model(project).name, now=spoken.name)
        return {"id": spoken.id, "name": spoken.name, "why": said, "by": "map"}
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


def off_map(project, model_id: str | None) -> str:
    """The refusal when the director would switch a whole video against Reed's map (UGC off
    Omni 1.2, or an animated style onto it) without a person asking; "" when it fits. Auto
    (None) is the style's own model."""
    from app import guides

    real = looks.base(looks.drawn(project)) in PHOTOREAL
    if model_id is None or (model_id == OMNI) == real:
        return ""
    style = guides.style(looks.drawn(project))["name"]
    return WHOLE.format(style=style, model="Omni 1.2" if real else "Seedance")


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
    if found.id == OMNI and not reason.strip():
        return NO_REASON
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
    resolution, shape and up to 6 reference pictures. Seedance's audio lines become one short
    sound line (no one speaking says so, as there's no sound switch: a narrated video keeps its
    narration throughout, Reed, 5 Nov); references are named in words by their order, the
    opening still as a guide, never a literal first frame; a one-shot clip asks for one
    continuous shot. Extra people are said in words before this (`unsent`)."""
    if model.id != OMNI:
        return input, files
    pictures = files.get("reference_images", [])[: model.max_reference_images]
    asked = input["prompt"]
    audio = AUDIO.search(asked)
    room = (m.group(1) if audio and (m := ROOM.search(audio.group(0))) else PLACE).strip()
    body = AUDIO.sub("", asked).strip()
    prompt = FIRST.sub(lambda m: _guide(m, body, len(pictures)), body)
    prompt = IMAGE.sub(lambda m: _picture(int(m.group(1)), len(pictures)), prompt)
    if len(SHOT.findall(prompt)) <= 1:
        prompt += f"\n{ONE_SHOT}"
    if not input.get("generate_audio"):
        prompt += "\n" + SILENT.format(room=room)
    elif audio:
        prompt += "\n" + SPOKEN.format(room=room)
    shaped = {"prompt": prompt, "duration": max(model.duration.min, min(input["duration"],
              model.duration.max)), "resolution": resolution(model),
              "aspect_ratio": input["aspect_ratio"]}  # fmt: skip
    return shaped, {"reference_images": pictures} if pictures else {}


def unsent_people(model_id: str, images: list[str]) -> tuple[str, ...]:
    """On Omni, the characters past its first two people (each has one sheet, within its 3 a
    person): left out of the pictures and described in words instead (clip_takes._in_words)."""
    people = [i for i in images if i.startswith("char:")]
    return tuple(people[PEOPLE:]) if model_id == OMNI else ()


def _guide(m: re.Match, prompt: str, sent: int) -> str:
    """`[Image1] is the first frame` → "The first reference picture guides the opening"."""
    picture = _picture(int(m.group(1)), sent)
    said = f"{picture} guides the opening picture (not an exact first frame)"
    before = prompt[: m.start()].rstrip(" ")
    return said[0].upper() + said[1:] if not before or before.endswith((".", "\n")) else said


def _picture(n: int, sent: int) -> str:
    """[Image2] → "the second reference picture" (one past the six sent: "a picture")."""
    return f"the {ORDINAL[n - 1]} reference picture" if 0 < n <= min(sent, 6) else "a picture"
