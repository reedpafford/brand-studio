"""Reed's model map (4 Nov): which model makes what, and what each needs sent. A presenter
talker is HeyGen Avatar IV from a still with our MiniMax voice; Omni (Gemini Omni 1.1) only for
the talker's own shots in more complex videos and storytelling, where they move, act or take
part in the story, never B-roll; B-roll is Seedance (2.0, or 1 Lite where enough), silent,
with sound effects added where they help. The director picks a clip's model from the guide
and says why (`choose`); the Clips tab shows each clip's model and why (`why`). Photoreal
Seedance B-roll (rule 10's exception, Reed, 4 Nov) describes the person from their approved
character description, in the same words in every prompt (clip_takes._in_words), instead of
attaching their photo or an opening still with them in it; products and screens stay
attached. Why: in th-20s (.context/tests/th-20s/REPORT.md) every Seedance 2.0 take sent a
photoreal teenager's photo was refused ("sensitive", E005) and 1 Lite refused it as invalid
input (E006), not charged. That test doesn't show every photoreal reference is refused, and
words don't guarantee the person looks the same in every shot. HeyGen, Omni and stylised
characters keep their references."""

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
ONLY_TALKER = ("Refused: Omni makes only the talker's own shots, where they move, act or take "
               "part in the story; never B-roll (Reed's model map).")  # fmt: skip
NO_TALKER = "Refused: this video has no talker, so Omni has nothing to make here."
SAYS_IT = ("Refused: this clip is the talker saying the narration to the lens, cut from their "
           "HeyGen take in our own voice, which Omni can't lip-sync. Omni makes the talker's "
           "shots where they act without speaking to the lens.")  # fmt: skip
NOT_VIDEO = "Refused: there's no video model called {}."
UNAPPROVED = ("Refused: Omni makes only the approved plan's acting and storytelling shots; "
              "approve the plan first.")  # fmt: skip
WHOLE_TAKE = "Refused: HeyGen makes the talker's one take, not a clip. Use make_take for B-roll."
PERSONS = "Refused: {who} chose {model} for this video's clips themselves; their choice stays."
SUNG = "Refused: this clip's shots are sung, so it needs a model that lip-syncs to the song."
SHAPE = "Refused: {model} makes {shapes} videos only; this one is {shape}."
LONG = "Refused: this clip is {seconds} s and {model} makes about {most} s at most."
EDGE = 0.05  # seconds: a sentence timed this close to a clip's edge is inside it
OMNI_WORDS = 25  # batch-b: about 25 words in Omni's 10 s clip
SAYS = ('Sound: the talker says, word for word and nothing else: "{words}" Voice: {voice}, the '
        "same voice in every clip. No one else speaks. No music.")  # fmt: skip
SPEAKS = (" The talker says it in Omni's own voice, described as \"{voice}\" in every clip, not "
          "the narrator's: the narration is muted only while they say it.")  # fmt: skip
OMNI_ONLY = "Refused: only Omni speaks in its own voice; this model's clip stays under the voice."
NARRATION_ONLY = ("Refused: a person asked for narration only in this video, so the talker "
                  "doesn't speak on Omni here.")  # fmt: skip
NO_WORDS = "Refused: no scripted words are said during this clip, so there's nothing to speak."
TOO_MANY = ("Refused: this clip's words are {n} long; Omni says about {most} in a clip. Split "
            "the clip at a phrase, then try again.")  # fmt: skip
NO_VOICE = ("Refused: describe the talker's voice for Omni first, in `note` (age, sex, pitch, "
            "pace, accent, mood): the same words go in every clip.")  # fmt: skip
SAME_VOICE = ('Refused: the talker\'s Omni voice is already "{voice}" in this video; one voice '
              "is described the same in every clip. Leave `note` empty to use it.")  # fmt: skip
SILENT = (
    "Sound: the talker doesn't speak to the lens in this shot; no one talks, only the "
    "sounds of the place. No music."
)  # Omni's sound, kept quiet under the narration


def _model(model_id: str):
    from app.catalogue import get_model

    return get_model(model_id)


def of_clip(project, clip):
    """The clip's model: its own (the director's choice) when it has one; Omni for a talker's
    shot when the presenter acts in the story; else the video's."""
    from sqlalchemy.orm import object_session

    from app.breakdown import video_model

    own = _model((clip.model or {}).get("id", "")) if clip is not None else None
    db = object_session(project)
    if own is None and clip is not None and db is not None and acts(db, project, clip):
        own = _model(OMNI)
    return own or video_model(project)


def acts(db, project, clip) -> bool:
    """A talker's shot in a video whose presenter acts in the story (Reed's L3): on Omni."""
    from app import host

    return host.how(project) == "acts" and shows_talker(db, project, clip)


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
    if acts(db, project, clip):
        found = _model(OMNI)
        return {"id": found.id, "name": found.name, "by": "map",
                "why": "The presenter acts in the story in this video: their shots are made on "
                       "Omni, which keeps their face from its picture."}  # fmt: skip
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


def said(db, project, clip) -> tuple[str, float, float] | None:
    """The script's words the narration says during this clip, exactly (its timed sentences
    inside the clip's piece of the narration), and when: (words, start, end); None: none."""
    from app.models.songs import SongTake

    take = db.get(SongTake, project.song_take_id) if project.song_take_id else None
    piece = clip.song_slice or {}
    if take is None or not take.timing or "start" not in piece:
        return None
    inside = [ln for ln in take.timing.get("lines") or []
              if ln.get("start") is not None and ln["start"] >= piece["start"] - EDGE
              and ln["end"] <= piece["end"] + EDGE]  # fmt: skip
    if not inside:
        return None
    return " ".join(ln["text"] for ln in inside), inside[0]["start"], inside[-1]["end"]


def speaks(clip, project) -> bool:
    """The talker says this clip's words on Omni: the director's choice, unless a person asked
    for narration only in this video (then the clip goes back under the voice, to be made
    again)."""
    return bool((clip.model or {}).get("speaks")) and not project.narration_only


def spoken(db, project, clips) -> dict[int, tuple[float, float]]:
    """For the cut: each clip whose talker says its lines on Omni, and when the narration is
    muted (only while those lines are said)."""
    out = {}
    for n, clip in enumerate(clips):
        if speaks(clip, project) and (found := said(db, project, clip)):
            out[n] = (found[1], found[2])
    return out


def speech(db, project, clip) -> tuple[str, str] | None:
    """(the words, the voice) a speaking Omni clip is asked to say them in; else None."""
    found = said(db, project, clip) if speaks(clip, project) else None
    return (found[0], project.omni_voice or "") if found else None


def _to_lens(db, project, clip) -> bool:
    """The plan has the talker saying this clip to the lens (on HeyGen, or on Omni when the
    director chose it)."""
    from app import talker
    from app.models.breakdowns import BreakdownVersion

    bd = db.get(BreakdownVersion, clip.breakdown_id or 0)
    return bool(bd) and talker.on(db, project) and talker._spoken(bd.data, clip.clip_id)


def _speaking(db, project, clip, voice: str) -> str:
    """Why a talker can't speak this clip on Omni ("" when they can). The video's Omni voice
    is kept by `choose` once every check passes (the same words go in every clip)."""
    if project.narration_only:
        return NARRATION_ONLY
    found = said(db, project, clip)
    if found is None:
        return NO_WORDS
    if len(found[0].split()) > OMNI_WORDS:
        return TOO_MANY.format(n=len(found[0].split()), most=OMNI_WORDS)
    voice = described(voice)
    if not (project.omni_voice or voice):
        return NO_VOICE
    if project.omni_voice and voice and voice != project.omni_voice:
        return SAME_VOICE.format(voice=project.omni_voice)
    return ""


def described(voice: str) -> str:
    return " ".join((voice or "").split())[:300]


def choose(db, project, clip, model_id: str | None, reason: str, speak: bool = False,
           voice: str = "") -> str:  # fmt: skip
    """The director's model for one clip (null: back to the video's), checked against the
    model map, with its new price said first. It never changes the video's own model. `speak`:
    the talker says this clip's scripted words on Omni, in Omni's own voice (`voice`, described
    once and the same in every clip), with the narration muted under them (Reed, 4 Nov: for a
    dramatic moment, an interaction, a reveal or a punchline, not merely movement)."""
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
        to_lens = _to_lens(db, project, clip)
        if to_lens and not speak:
            return SAYS_IT
        if not to_lens and not shows_talker(db, project, clip):
            return ONLY_TALKER
        if speak and (no := _speaking(db, project, clip, voice)):
            return no
    elif speak:
        return OMNI_ONLY
    elif who := _persons(db, project):
        return PERSONS.format(who=who, model=_model(project.video_model).name)
    if (clip.song_slice or {}).get("sung_shots") and not found.lip_sync and not speak:
        return SUNG
    if project.aspect_ratio not in found.aspect_ratios:
        return SHAPE.format(model=found.name, shapes=" or ".join(found.aspect_ratios),
                            shape=project.aspect_ratio)  # fmt: skip
    most = found.fixed_seconds or found.duration.max
    if clip.seconds > most:
        return LONG.format(seconds=clip.seconds, model=found.name, most=most)
    then = take_credits(db, project, clip)  # a take's whole price, its check included
    clip.model = {"id": found.id, "why": reason.strip()[:300], "by": "director",
                  **({"speaks": True} if speak else {})}  # fmt: skip
    now = take_credits(db, project, clip)
    if speak:
        project.omni_voice = project.omni_voice or described(voice)
    told = (
        f"Clip {clip.clip_id.removeprefix('c')} is made on {found.name} now: up to "
        f"{now:.1f} credits a take (was {then:.1f} on {was.name}). Why: {reason.strip()}"
    )
    if speak:  # never a silent change of an established voice: said before any take
        told += SPEAKS.format(voice=project.omni_voice)
    return told


def fit(model, input: dict, files: dict, speech: tuple[str, str] | None = None
        ) -> tuple[dict, dict]:  # fmt: skip
    """A take's input as a talker-only model reads it (Omni: prompt, resolution, shape and its
    reference pictures; no duration, no sound switch, its own sound always). In a narrated
    video the narration is the talker's one voice, so on Omni they act without speaking to the
    lens and its own sound stays quiet under the voice; unless the clip is theirs to say
    (`speech`: the script's words exactly, in the video's one Omni voice description)."""
    if not model.talker_only:
        return input, files
    sound = SILENT if speech is None else SAYS.format(words=speech[0], voice=speech[1])
    shaped = {"prompt": f"{input['prompt']}\n{sound}", "resolution": resolution(model),
              "aspect_ratio": input["aspect_ratio"]}  # fmt: skip
    pictures = files.get("reference_images", [])[: model.max_reference_images]
    return shaped, {"reference_images": pictures} if pictures else {}
