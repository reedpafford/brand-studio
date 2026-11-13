"""Reed's model map (4 Nov, changed 6 Nov): which model makes what, and what each needs sent.
Each style has its own video model (Reed, 6 Nov: "keep seedance for the animated and
expression-full ones for now. Omni is more for the realistic stuff"; "1.2 replaces 1.1"): Seedance
2.5 for House and Disney Pixar (and songs), Seedance 2.0 for Skeleton, Claymation, Zack D and Dr.
Pickle, and Gemini Omni 1.2 for UGC. A real-looking style (`PHOTOREAL`) keeps every clip on the
model its guide names (`video_model:`), Movie's too: talking, wordless or an insert, in that
model's own voices. In UGC, how the presenter appears (host.how) decides the talker: one who
stays in one spot the whole time (talks, or in a corner) is one HeyGen Avatar IV take from a
still, lip-synced to our own voice track (a talker's is the MiniMax voice), and Omni 1.2 makes
only the B-roll around them; one who moves around in the story (acts) has no take of their own,
so their shots are made on Omni 1.2 like the B-roll. Every UGC clip that isn't the HeyGen talker
stays on Omni 1.2 (`choose`). Omni always makes its own sound and takes no audio: in a shot where
no one speaks its prompt says so, and a narrated video keeps its narration throughout (Reed,
5 Nov). The Clips tab shows each clip's model and why (`why`).
Photoreal Seedance (rule 10's exception, Reed, 4 Nov: on Replicate's everyone, on KIE's only
someone whose sheet Seedream didn't draw, `unsent`) describes the person from their approved
character description, in the same words in every prompt (clip_takes._in_words), instead of
attaching their photo or an opening still with them in it; products and screens stay attached.
Why: in th-20s (.context/tests/th-20s/REPORT.md) every Seedance 2.0 take sent a photoreal
teenager's photo was refused ("sensitive", E005) and 1 Lite refused it as invalid input (E006),
not charged. HeyGen, Omni and stylised characters keep their references."""

import re

from app import looks

PHOTOREAL = ("ugc", "movie")  # styles whose people look real: clips stay on the guide's model


def unsent(look: str | None, model_id: str, shots: list[dict], images: list[str] = (),
           drawn: tuple[str, ...] = ()) -> tuple[str, ...]:  # fmt: skip
    """The references a take leaves out and describes in words instead: in a photoreal style
    on Seedance, every character sheet, and the opening still when someone is in it. KIE's
    Seedance takes the sheets Seedream drew (`drawn`, sheets.seedream_drew), so it gets those:
    a sheet from a photo, or one Nano Banana drew, is refused there as it is on Replicate."""
    if not model_id.startswith("seedance") or looks.base(look or looks.DEFAULT) not in PHOTOREAL:
        return ()
    kie = (model := _model(model_id)) is not None and model.provider == "kie"
    sheets = tuple(i for i in images if i.startswith("char:") and i not in drawn) if kie else (
        "char:",)  # fmt: skip
    return (*sheets, "frame:") if any(s.get("character_ids") for s in shots) else sheets


# --- The model each clip is made with, and why (v6 F: the Clips tab's "Model" and "Why") -------

OMNI = "gemini-omni-1.2"
OMNI_1_1 = "gemini-omni-1.1"
NOT_VIDEO = "Refused: there's no video model called {}."
WHOLE_TAKE = "Refused: HeyGen makes the talker's one take, not a clip. Use make_take for B-roll."
SAYS_IT = (
    "Refused: this clip is the talker saying the narration to the lens in one spot, cut "
    "from their one HeyGen take in our own voice (Reed, 6 Nov): it stays on HeyGen."
)
REAL = ("Refused: in UGC every clip that isn't the HeyGen talker is made on Omni 1.2, the B-roll "
        "and a talker who moves around in the story (Reed, 6 Nov: \"Omni is more for the "
        "realistic stuff\").")  # fmt: skip
ONE_MODEL = ("Refused: in {style} every clip is made on {model}, the talking, the wordless "
             "and the inserts, in its own voices.")  # fmt: skip
NO_REASON = ("Refused: say in `why` what this shot needs from Omni 1.2; it's shown on the clip "
             "(Reed, 6 Nov: \"with its reason shown\").")  # fmt: skip
WHOLE = ("Refused: {style}'s videos are made on {model}. Switch the whole video only when a "
         "person asks in the chat (name their note).")  # fmt: skip
PERSONS = "Refused: {who} chose {model} for this video's clips themselves; their choice stays."
SUNG = "Refused: this clip's shots are sung, so it needs a model that lip-syncs to the song."
SHAPE = "Refused: {model} makes {shapes} videos only; this one is {shape}."
LONG = "Refused: this clip is {seconds} s and {model} makes about {most} s at most."
# Omni's prompt, in the order Google's Flow guide gives (camera, then subject and action, the
# line as `Dialogue: … says, "…"`, context, style, audio; Reed, 11 Nov: "Words and dialogue
# should be prompted exactly as google flow recommends") and docs/prompting/omni-1.2.md: no
# sound switch, so one audio line (§5); references named by order (§2, §6); a clip's own start
# frame sent as the start frame, alone (row 3); one shot asked for in words (§3)
SILENT = "Audio: no one speaks (no voices, narration or dialogue), only {room}. No music."
SPOKEN = ("Audio: only the quoted lines are spoken, word for word, in American English, each "
          "by the person named, with {room}. No music.")  # fmt: skip
PLACE = "the sounds of the place"
ONE_SHOT = "One continuous shot."
FROM_FRAME = "It starts on the start frame given, in the same light and colour."
# a take made at Omni's nearest shape is cropped to the video's in the cut (`nearest`)
FRAMED = ("Framing: this shot is cropped to {shape} in the edit, so keep the action and faces "
          "inside the centre {area}.")  # fmt: skip
ROOM = re.compile(r"\bonly (?:the spoken lines and )?(.+?)\. No music", re.I)
IMAGE = re.compile(r"\[Image(\d+)\]")
HEAD = re.compile(r"^(Audio|References|Language|Summary|Style|Setting|Keep):\s*(.*)$")
SHOT = re.compile(r"^Shot \d+ \| ([\d.]+)-([\d.]+) s\.\s*(.*)$")
VOICE = re.compile(r"^.{1,60}'s voice: ")
LIST = re.compile(r"Shots?\b[^.]*:$")
# a shot's line as the house prompt writes it: 'Mom (in English, warm): "…"'
SAID = re.compile(r'^(?P<seen>.*?)\s*(?P<who>[^.()"“]+?)(?: \((?P<how>[^)]*)\))?: '
                  r'(?P<line>["“].*)$', re.S)  # fmt: skip
THOUGHT = re.compile(r"voice-?over|lips closed|inner voice|thought|V\.O\.", re.I)
ORDINAL = ("first", "second", "third", "fourth", "fifth", "sixth")
PEOPLE = 2  # Omni: 2 people a clip, 3 pictures each (§6); each sends one sheet
PICTURES = 6  # Omni's reference pictures at most (the catalogue's max_reference_images)


def _model(model_id: str):
    """A model a clip may be made on: never Omni 1.1 (back 12 Nov only for a line 1.2 refuses:
    "1.2 replaces 1.1" stands), so a clip that names it reads as the video's model."""
    from app.catalogue import get_model

    return None if model_id == OMNI_1_1 else get_model(model_id)


def billed(model, seconds: int) -> int:
    """The seconds a take of a clip is asked for on `model`, and so charged and recorded at:
    the clip's own length within what the model makes (a 3 s clip fitted to Omni 1.2, made on
    Seedance, is asked for, billed and recorded at Seedance's 4 s: Reed, accurate spend)."""
    d = model.duration
    return max(d.min, min(seconds, d.max)) if d is not None else seconds


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
    """The refusal when the director would switch a whole video against Reed's map (a
    real-looking style off its guide's model, or an animated style onto Omni 1.2) without a
    person asking; "" when it fits. Auto (None) is the style's own model."""
    from app import guides

    style = guides.style(looks.drawn(project))
    real = looks.base(looks.drawn(project)) in PHOTOREAL
    if model_id is None or (model_id == style["video_model"] if real else model_id != OMNI):
        return ""
    own = _model(style["video_model"]).name if real else "Seedance"
    return WHOLE.format(style=style["name"], model=own)


def choose(db, project, clip, model_id: str | None, reason: str) -> str:
    """The director's model for one clip (null: back to the video's), checked against the
    model map, with its new price said first and its reason shown. It never changes the video's
    own model. A talker in one spot stays on HeyGen and the rest of UGC on Omni 1.2 (Reed,
    6 Nov); Movie's clips stay on its guide's model unless a person's note asks; in an
    animated style Omni may make a realistic shot."""
    from app import guides, talker
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
    if found.id != was.id and _too_long(db, project, clip, was, reason):
        from app.clip_takes import failed_fits

        then = ASK_OWNER if failed_fits(db, clip) >= 2 else REWRITTEN
        return LENGTH.format(n=clip.clip_id.removeprefix("c"), model=was.name, then=then)
    if talker.says(db, project, clip):
        return SAYS_IT
    if who := _persons(db, project):
        return PERSONS.format(who=who, model=_model(project.video_model).name)
    real = looks.base(looks.drawn(project))
    if real in PHOTOREAL and found.id != (own := guides.style(real)["video_model"]):
        from app.settings_move import ASKED

        if real == "ugc":
            return REAL
        if not ASKED.search(reason or ""):  # a person's note may ask for one clip off it
            return ONE_MODEL.format(style=guides.style(real)["name"], model=_model(own).name)
    if found.id == OMNI and not reason.strip():
        return NO_REASON
    if (clip.song_slice or {}).get("sung_shots") and not found.lip_sync:
        return SUNG
    if project.aspect_ratio not in found.aspect_ratios and found.id != OMNI:  # Omni: cropped
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


LENGTH = ("Refused: clip {n}'s prompt is too long for {model}, and a clip moves to another "
          "model only for what its shots need or a person's note (name it), never to get past "
          "that: {then}")  # fmt: skip
REWRITTEN = "its prompt is rewritten to fit, free. Make its take once it's rewritten."
ASK_OWNER = ("both rewrites to fit are used, so ask the owner: they can shorten it with Edit "
             "(free) or move it to another model.")  # fmt: skip


def _too_long(db, project, clip, was, reason: str) -> bool:
    """The move's reason is its prompt's length (video 268: c3 moved to Seedance 2.5, dearer,
    after its prompt was refused): too long for its model as a take sends it (its people said
    in words too), or being rewritten to fit."""
    from fastapi import HTTPException

    from app.clip_prompts import fixing
    from app.clip_takes import take_input
    from app.settings_move import ASKED

    if ASKED.search(reason or "") or not was.prompt_max:
        return False
    try:
        sent = take_input(db, project, clip, check=False)["input"].get("prompt") or ""
    except HTTPException:  # it can't be sent yet (a look missing): its prompt as written
        sent = clip.prompt or ""
    return len(sent) > was.prompt_max or bool(fixing(db, clip))


def fit(model, input: dict, files: dict) -> tuple[dict, dict]:
    """A take's input as Omni reads it: the prompt in Flow's order (`_flow`), duration (3–15
    s), resolution and shape, and either the clip's own start frame, alone (`image`: Omni
    takes a start frame or references, never both), or up to 6 reference pictures. No one
    speaking says so, as there's no sound switch: a narrated video keeps its narration
    throughout (Reed, 5 Nov). Extra people are said in words before this (`unsent`). KIE's
    Seedance gets only its prompt re-laid (`_scene`)."""
    if model.provider == "kie":
        return {**input, "prompt": _scene(input["prompt"])}, files
    if model.id != OMNI:
        return input, files
    start = files.get("image", [])[:1]
    pictures = [] if start else files.get("reference_images", [])[: model.max_reference_images]
    prompt = _flow(input["prompt"], len(pictures), bool(start), bool(input.get("generate_audio")))
    if (shape := nearest(input["aspect_ratio"], model.aspect_ratios)) != input["aspect_ratio"]:
        area = "square" if input["aspect_ratio"] == "1:1" else f"{input['aspect_ratio']} area"
        prompt += "\n" + FRAMED.format(shape=input["aspect_ratio"], area=area)
    shaped = {"prompt": prompt, "duration": max(model.duration.min, min(input["duration"],
              model.duration.max)), "resolution": resolution(model),
              "aspect_ratio": shape}  # fmt: skip
    sent = {"image": start} if start else {"reference_images": pictures} if pictures else {}
    return shaped, sent


def _flow(prompt: str, sent: int, start: bool, speaks: bool) -> str:
    """The house clip prompt (its Audio, References, Style, Setting, voice and Shot lines) as
    Flow lays a video prompt out: each shot (camera, action, its line), the setting, the
    references by their order, the style, then the voices and one audio line. The Summary
    (it says the lines again in other words, and Omni said them: video 390), the Keep line
    and the Language line go: the audio line says the language once."""
    part = _parts(prompt)
    shots = part.get("Shot", [])
    room = ROOM.search(" ".join(part.get("Audio", [])))
    out = [_shot(x, len(shots) > 1) for x in shots]
    out += [f"Setting: {x}" for x in part.get("Setting", [])]
    out += part.get("", [])
    if sent:
        out += [f"References: {x}" for x in part.get("References", [])]
    one = [ONE_SHOT] * (len(shots) <= 1) + [FROM_FRAME] * start
    out.append(" ".join(["Style:", *part.get("Style", []), *one]) if part.get("Style") or one
               else "")  # fmt: skip
    out += part.get("Voice", [])
    speaks = speaks or any("\nDialogue: " in x for x in out)  # a thought is heard too (398)
    out.append((SPOKEN if speaks else SILENT).format(room=(room[1] if room else PLACE).strip()))
    said = IMAGE.sub(lambda m: _picture(int(m[1]), sent), "\n".join(filter(None, out)))
    return re.sub(r"(?<=[.:] )the (?=\w+ image is )", "The ", said)


def _parts(prompt: str) -> dict[str, list[str]]:
    """The house clip prompt's lines by name (Audio, References, Summary, Style, Setting, Keep,
    "Shot", "Voice"; "" for any other), each without its name; a list's head ("Shots:") goes."""
    part: dict[str, list[str]] = {}
    for line in (x for x in prompt.splitlines() if x.strip() and not LIST.match(x)):
        m = HEAD.match(line)
        key = "Shot" if SHOT.match(line) else "Voice" if VOICE.match(line) else m[1] if m else ""
        part.setdefault(key, []).append(m[2] if m else line)
    return part


def _said(line: str) -> tuple[str, str, str, tuple[str, bool, str, str] | None]:
    """A house shot line as (start, end, what is seen, its spoken line): the line as (who,
    whether it is only thought, how it is said, the quoted words), or None when no one speaks."""
    a, b, text = SHOT.match(line).groups()
    text = text.replace(" No one speaks.", "").replace("No one speaks.", "").strip()
    if not ((d := SAID.match(text)) and d["who"].strip()):
        return a, b, text, None
    how = [x.strip() for x in (d["how"] or "").split(",")]
    how = [x for x in how if x and x.lower() not in ("in english", "in american english")]
    told = ", ".join(x for x in how if not THOUGHT.search(x))
    inner = any(THOUGHT.search(x) for x in how)
    return a, b, d["seen"].strip(), (d["who"].strip(), inner, told, d["line"])


def _shot(line: str, many: bool) -> str:
    """One shot as Flow writes it: its time in brackets when the clip has several, the camera
    and the action as the plan gave them, then `Dialogue: Mom says, "…"` with how it is said
    after it (a thought: heard as a voice-over, lips closed)."""
    a, b, text, said = _said(line)
    if said:
        who, inner, told, words = said
        tag = f"{who} thinks, heard as a voice-over with lips closed" if inner else f"{who} says"
        text = (f"{text}\nDialogue: {tag}, {words}"
                + (f" Delivery: {told}." if told else "")).strip()  # fmt: skip
    clock = lambda t: f"00:{float(t):04.1f}".replace(".0", "")  # noqa: E731
    return (f"[{clock(a)}-{clock(b)}] " if many else "") + text


# One picture's sentence in the References line, to where the next begins ("[Image2] is the
# place, INT. BAR - NIGHT."), and what KIE's Seedance is told to take from a person or a place
PICTURE = re.compile(
    r"\[Image(\d+)\] is (.+?)\.(?=\s+\[Image\d+\] is |\s+[^.\[]+\([^)]*\) is |\s*$)"
)
PERSON = "their face, hair and outfit"
A_PLACE = "use it for the place, its light and colour, not for framing"


def _scene(prompt: str) -> str:
    """The house clip prompt as KIE's Seedance was sent it in the clips that held their people
    (Reed, 12 Nov; .context/rp5): `Scene context:` (the Summary), a line for each picture
    saying what to take from it, the shots with their times and lines, then one `Look:` line
    (the Style and the Setting) and one `Sound:` line ending on the voices. The repeated Audio
    line, the Keep line (each sheet's own line says it) and the Language line go. A prompt
    with no house shots (a sample, a Freestyle clip) is sent as written."""
    part = _parts(prompt)
    if not part.get("Shot"):
        return prompt
    people = set(re.findall(r"as in \[Image(\d+)\]", " ".join(part.get("Keep", []))))

    def job(m: re.Match) -> str:
        take = PERSON if m[1] in people else A_PLACE if m[2].startswith("the place, ") else ""
        return f"[Image{m[1]}] is {m[2]}: {take}." if take else m[0]

    out = [f"Scene context: {x}" for x in part.get("Summary", [])]
    for x in part.get("References", []):
        out += re.split(r"\s+(?=\[Image\d+\] is )", PICTURE.sub(job, x))
    speaks = False
    for n, x in enumerate(part["Shot"], 1):
        a, b, text, said = _said(x)
        if said:
            who, inner, told, words = said
            tag = f"{who}'s thought is heard as a voice-over, lips closed" if inner else (
                f"{who} says")  # fmt: skip
            text, speaks = f"{text} {tag}{', ' + told if told else ''}: {words}".strip(), True
        out.append(f"Shot {n}, {a}-{b} s: {text}")
    out += part.get("", [])
    out.append(" ".join(["Look:", *part.get("Style", []), *part.get("Setting", [])]))
    room = ROOM.search(" ".join(part.get("Audio", [])))
    heard = "; ".join(x.replace("'s voice: ", ", ", 1).rstrip(".") for x in part.get("Voice", []))
    room = (room[1] if room else PLACE).strip()
    sound = [f"Sound: {room[:1].upper()}{room[1:]}.",
             (f"Voices: {heard}." if heard else "") if speaks else "No one speaks.",
             "No music, no subtitles."]  # fmt: skip
    out.append(" ".join(filter(None, sound)))
    return "\n".join(out)


def nearest(shape: str, shapes: list[str]) -> str:
    """The shape a model makes for the video's `shape`: its own when the model has it, else
    the nearest one it does, 9:16 on a tie (Omni 1.2 makes only 9:16 and 16:9: a 1:1 video's
    takes on it are made 9:16 and the cut crops them to 1:1, QA on #1440)."""
    import math

    def ratio(s: str) -> float:
        w, _, h = s.partition(":")
        return float(w) / float(h)

    given = [s for s in shapes if re.fullmatch(r"\d+:\d+", s)]
    if shape in shapes or not given or not re.fullmatch(r"\d+:\d+", shape or ""):
        return shape
    return min(given, key=lambda s: (round(abs(math.log(ratio(s) / ratio(shape))), 6),
                                     s != "9:16"))  # fmt: skip


def left_out(look: str | None, model_id: str, shots: list[dict], images: list[str],
             drawn: tuple[str, ...] = ()) -> tuple[str, ...]:  # fmt: skip
    """Every reference a take on this model leaves out and says in words instead."""
    return unsent(look, model_id, shots, images, drawn) + unsent_pictures(model_id, images)


def unsent_pictures(model_id: str, images: list[str]) -> tuple[str, ...]:
    """On Omni, the characters past its first two people (each has one sheet, within its 3 a
    person), then, while the pictures still pass its six, the places and the opening still:
    left out and said in words instead (clip_takes._in_words), so a product or a screen is
    never the picture its limit cuts (video 284: the real pouch must reach the clip)."""
    if model_id != OMNI:
        return ()
    out = [i for i in images if i.startswith("char:")][PEOPLE:]
    over = len(images) - len(out) - PICTURES
    for kind in ("place:", "frame:"):
        for i in images:
            if over > 0 and i.startswith(kind):
                out.append(i)
                over -= 1
    return tuple(out)


def _picture(n: int, sent: int) -> str:
    """[Image2] → "the second image" (one past the six sent: "a picture")."""
    return f"the {ORDINAL[n - 1]} image" if 0 < n <= min(sent, 6) else "a picture"
