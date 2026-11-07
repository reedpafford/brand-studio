"""Output schemas for each Claude step. Claude reads the field descriptions, so they are part
of the prompt. No numeric or length constraints here: structured outputs ignore them, so limits
are stated in the descriptions and checked in `check.py`.

Asset ids are strings with a kind prefix, as listed in the brand block and the user message:
`screen:12`, `char:5`, `place:3`, `prop:7`, `frame:c2`."""

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema

# --- Enhance: suggestions anchored to the editor's script ---


class Anchor(BaseModel):
    line: int = Field(description="Line number (from the numbered script) where the quote is.")
    quote: str = Field(
        description="Text copied exactly from that line, character for character, without the "
        "line-number prefix. A few words up to the whole line; the server finds it to place "
        "the mark, so it must be unique enough on that line."
    )


class Suggestion(BaseModel):
    id: str = Field(description="s1, s2, … in script order.")
    kind: Literal["camera", "action", "reaction", "brand_screen"]
    anchor: Anchor
    placement: Literal["before", "after"] = Field(
        description="Whether the mark goes on its own line just before or just after the quoted "
        "line. The script's own lines never change."
    )
    text: str = Field(
        description="What we see, in script style, present tense, one line; never spoken words. "
        "brand_screen: the screen line ('★ fomo screen: Token chart up — on Leo's phone in his "
        "hand')."
    )
    screen_id: str | None = Field(
        description="brand_screen only: the screen's or product's id from the brand block "
        "(screen:N or product:N). Otherwise null."
    )
    reason: str = Field(
        description="One short plain sentence for the editor: what this does for the hook, "
        "the story, the emotion, the pace, or the brand."
    )


class Note(BaseModel):
    line: int = Field(description="The numbered line the note is about.")
    text: str = Field(
        description="One plain sentence: what only the editor can fix in the words and why "
        "(e.g. the line says peanut butter, the bag says chicken). Never replacement words."
    )


class EnhanceResult(BaseModel):
    suggestions: list[Suggestion] = Field(
        description="In script order. Only suggestions that clearly help; an empty list if the "
        "script already plays well."
    )
    notes: list[Note] = Field(description="Usually empty. Things in the words, not edits.")


# --- Script draft from a brief ---


class ScriptDraft(BaseModel):
    hook_idea: str = Field(description="The hook in a few words, e.g. 'Mom finds the wallet'.")
    script: str = Field(
        description="The full script in the house format, sized to the planned length at about "
        "4.8 spoken words per second while someone speaks, with silent beats between."
    )
    changed_lines: list[str] = Field(
        default_factory=list,
        description="When adapting a reference: each of its spoken lines this draft rewrites "
        "for the brand swap, as written in the draft (not the end line). Empty otherwise.",
    )


class ScriptDrafts(BaseModel):
    drafts: list[ScriptDraft] = Field(
        description="2 or 3 drafts, each with a clearly different hook; the story after the "
        "hook may stay the same."
    )


# --- Variations: alternates of an approved script (workflow v2, #189) ---


class Variation(BaseModel):
    title: str = Field(description="2–4 words for the script library, e.g. 'The car'.")
    premise: str = Field(description="One sentence: what this version changes and how it pays off.")
    script: str = Field(
        description="The full script in the house format: scene headings, action lines, "
        "NAME: words, and every ★ brand line the original has."
    )
    changes: list[str] = Field(
        description="What differs from the original, in plain words, one item each."
    )


class Variations(BaseModel):
    variations: list[Variation] = Field(
        description="Exactly the number asked for in <count>, each a different premise."
    )


# --- Cast slots: the roles every version needs a look for (Reed, #197) ---


class CastSlot(BaseModel):
    role: str = Field(
        description="The script's name and part, e.g. 'Nate, the groom' or 'Bruno, the "
        "pitbull (narrator)'; an unnamed role by its part, e.g. 'His owner'."
    )
    description: str = Field(
        description="Who they are, then how they look: starts with age range, gender and role "
        "or job ('Mid-40s woman, a primary-school teacher; …'), then build, hair or coat, skin, "
        "signature outfit. Plain and drawable; an original character (never one resembling a "
        "famous film, TV, comic or game character), no celebrity look-alikes, no logos."
    )
    guessed: list[Literal["age", "gender", "occupation"]] = Field(
        default_factory=list,
        description="Which of age, gender and occupation the scripts and brief don't say, so "
        "you inferred them from context. Empty when all three are stated.",
    )
    kind: Literal["Main", "Helper", "Rival", "Family"] = Field(
        description="Main for the hero and the story's other lead; Helper for a mentor, coach "
        "or friend; Rival for the one they're up against; Family for a parent, aunt or sibling."
    )
    appears_in: list[int] = Field(
        description="Version slots the role is in: 0 is the original, then 1 and 2."
    )
    recurring: bool = Field(description="True when the role is in two or more scenes or versions.")
    may_be_same_as: str = Field(
        default="",
        description="Only when you're unsure whether this is a named slot under another name: "
        "that slot's role, word for word (e.g. 'Kimchi, Nate's rich friend'). Empty otherwise.",
    )


class CastSlots(BaseModel):
    slots: list[CastSlot] = Field(
        description="Mains first, then in order of first appearance. Never background people "
        "(guests, crowds, admirers, extras) or one-shot passers-by."
    )


# --- Breakdown: scenes → shots → clips ---


class ScreenFigure(BaseModel):
    balance: str | None = Field(
        description="The total the screen shows, as it should read on screen, e.g. '$12,900'; "
        "or null."
    )
    change: str | None = Field(
        description="The gain or loss it shows, signed, e.g. '+$1,222' or '-$380'; or null."
    )


class Shot(BaseModel):
    id: str = Field(description="'<scene>.<shot>', e.g. '1.1', '1.2', '2.1'.")
    script_lines: list[int] = Field(description="Numbered script lines this shot covers.")
    speaker: str | None = Field(description="Who speaks in this shot (cast name), or null.")
    line: str | None = Field(
        description="The exact spoken words from the script, unchanged; null if nobody speaks. "
        "One speaker's line per shot."
    )
    action: str = Field(
        description="What we see happen, concretely, in one sentence. In a shot nobody speaks "
        "in, what the body does ('types back', 'nods'), never says, tells, replies or answers."
    )
    reaction: str | None = Field(
        description="Who reacts, the feeling and its reason, then how it shows at phone size, "
        "e.g. 'Tasha, touched he remembered her: eyes well, a shaky smile'; never words a "
        "character could say. Or null."
    )
    camera: str = Field(
        description="Size, angle and move, e.g. 'Low-angle close-up, fast push-in' or "
        "'Over-the-shoulder close-up on the phone in his hand, static'."
    )
    seconds: float = Field(
        description="Estimated length. Dialogue: words / 4.8 plus any held reaction. Silent "
        "reactions and inserts: 0.5–1.5."
    )
    character_ids: list[str] = Field(
        description="Cast ids on screen in this shot. Someone the script names on screen who "
        "has no id (they never speak, say): 'person:<Name>', as the script names them, never "
        "another's id."
    )
    place_id: str | None = Field(description="Place id from the user message, or null.")
    moment: str | None = Field(
        description="The brand moment this shot is, from the brand block's moments (e.g. "
        "'trading', 'win', 'loss'), or null."
    )
    screen_ids: list[str] = Field(
        description="Brand screens (screen:N) and the project's product (product:N) shown in "
        "this shot. Required whenever `moment` is one the brand block lists them for."
    )
    screen_figure: ScreenFigure | None = Field(
        default=None,
        description="Only when this shot shows a brand screen with a figure on it: the figure, "
        "for the first screen in screen_ids; the server draws it onto that screen. Each winning "
        "beat's figure is bigger than the last; a loss is signed '-'. Null otherwise.",
    )


class Scene(BaseModel):
    id: int = Field(description="1, 2, 3, …")
    heading: str = Field(description="'INT. BEDROOM — NIGHT' style.")
    look: str = Field(
        description="One sentence: palette, visible light, depth and background people, chosen "
        "to show the story state (cold and dark for the low point, warm or neon for the win)."
    )
    shots: list[Shot]


class Clip(BaseModel):
    id: str = Field(description="c1, c2, … in order.")
    shot_ids: list[str] = Field(description="Consecutive shots generated together as one clip.")
    seconds: int = Field(
        description="Sum of its shots, rounded up, within the video model's min and max length."
    )
    seam: str = Field(
        description="The hand-off: the beat the clip ends on and how the next clip's first shot "
        "answers it (a look, a sound, a matching pose, a white flash into a time jump), after "
        "the last line's reaction has landed. 'end' for the last clip."
    )


class Breakdown(BaseModel):
    hook: str = Field(
        description="What the first 2 seconds show and say, and why a scrolling viewer stops."
    )
    scenes: list[Scene]
    clips: list[Clip]


# --- Song ads (Reed, 2026-10-28): the song leads, the pictures follow its real timing ---


class SongShot(Shot):
    song_start: float = Field(description="Where it starts in the song, in seconds, on a beat.")
    song_end: float = Field(
        description="Where it ends, on a beat; the next shot starts here (no gaps)."
    )
    sung: bool = Field(
        description="True only when the script marks this line or section [Lip-sync]: the lead "
        "sings it on camera. Otherwise false: B-roll, silent picture under the song."
    )


class SongScene(Scene):
    shots: list[SongShot]


class SongBreakdown(Breakdown):
    scenes: list[SongScene]


class SongDirection(BaseModel):
    title: str = Field(description="The song's title, usually its hook line.")
    concept: str = Field(description="1–2 sentences: the song's vibe and the angle it sings.")
    lyrics: str = Field(
        description="The whole song, one sung line a line, with section tags on their own "
        "lines ([Verse 1], [Chorus], [Bridge]); the brand where the song brings it in, never "
        "forced into the last line."
    )
    style_line: str = Field(
        description="Under 25 words: genre, vocal, tempo or BPM, mood, production; never an "
        "artist or band name, e.g. 'indie pop, warm female lead, 104 BPM, playful, modern "
        "polished'."
    )
    visual_concept: str = Field(
        description="2–3 sentences: what's on screen at the key lyric moments, as animated "
        "B-roll in the video's style."
    )
    left_out: list[str] = Field(
        description="Adapting a <source> script: each beat, claim or line of it this direction "
        "leaves out, in a few words ('the vet quote'); empty when nothing is left out or the "
        "song is new."
    )
    unchecked_claims: list[str] = Field(
        description="Every claim the lyrics make about the product that the brand block doesn't "
        "state (a benefit, a number, an ingredient), word for word, for the editor to check; "
        "empty when every claim is the brand's own."
    )


class SongDirections(BaseModel):
    directions: list[SongDirection] = Field(description="Exactly 2, clearly different.")
    recommended: Literal[1, 2] = Field(description="The direction you'd pick for this brief.")


# --- Storyboard: one still per clip (or per shot) ---


class Frame(BaseModel):
    clip_id: str
    shot_id: str = Field(description="The shot this still shows (the clip's first shot).")
    prompt: str = Field(
        description="Image prompt for one still. Refers to the references in order as "
        "'image 1', 'image 2', …"
    )
    reference_ids: list[str] = Field(
        description="Asset ids passed as reference images, in the order the prompt uses them; "
        "no more than the image model's limit."
    )


class StoryboardFrames(BaseModel):
    frames: list[Frame]


# --- Clip prompts for the video model ---


class Reference(BaseModel):
    kind: Literal["image", "video", "audio"]
    id: str = Field(description="Asset id from the user message, e.g. 'frame:c1', 'screen:12'.")
    role: str = Field(
        description="What it is for, e.g. 'storyboard frame', 'Leo's look', 'fomo Token chart "
        "up screen, shown exactly'."
    )


class ClipPrompt(BaseModel):
    clip_id: str
    seconds: int = Field(description="The clip's length from the breakdown.")
    references: list[Reference] = Field(
        description="In order: images become [Image1], [Image2], … videos [Video1], … audios "
        "[Audio1], … Within the video model's limits."
    )
    prompt: str = Field(description="The video prompt, in the shape the system prompt shows.")


class ClipPrompts(BaseModel):
    clips: list[ClipPrompt]


# --- Change it: a still's or clip's prompt rewritten from a plain-English note ---


class ChangedPrompt(BaseModel):
    prompt: str = Field(description="The whole prompt with only the note's change made.")


# --- Quick clip: Improve prompt ---


class ImprovedPrompt(BaseModel):
    prompt: str = Field(description="The video prompt, in the shape the system prompt shows.")


# --- Look fit: does a made look read as its role? (Reed, "looks must fit the role") ---


class LookFit(BaseModel):
    fits: bool = Field(
        description="False only for a clear mismatch a viewer would notice at a glance: the "
        "wrong age range, the wrong gender, or an outfit that contradicts the job."
    )
    seen: str = Field(description="Who the sheet shows, in a few words: '8-year-old boy'.")
    problem: str = Field(
        description="When fits is false, what to change, as a plain instruction for redrawing "
        "('draw an adult woman in her 40s, not a child'); '' when it fits."
    )
    role_name: str = Field(
        default="",
        description="Only when <role_text>'s name says something the sheet plainly contradicts "
        "('Biscuit, the golden dog' for a French bulldog): the name rewritten to match, word "
        "for word up to its first comma ('Biscuit, the French bulldog'). Empty otherwise.",
    )
    role_description: str = Field(
        default="",
        description="Only when <role_text> says something the sheet plainly contradicts "
        "(species, breed, colouring, hair, age range, gender): the whole text rewritten to "
        "match the sheet, changing only what contradicts it. Empty otherwise.",
    )


# --- Reel watch: Gemini reads an imported reel (reel import, Reed #270). Not a Claude step:
# Gemini gets this schema as JSON in its prompt (`prompts.watch_system()`) and the server
# validates the answer with ReelWatch. Words and times come from prep, never from Gemini. ---


class WatchHook(BaseModel):
    seconds: float = Field(description="Where the hook ends, in seconds (usually 1–5).")
    mechanic: str = Field(
        description="What grabs in those seconds, e.g. \"'I do' → 'HELL NO!': rejected at "
        'the altar, ring thrown".'
    )


class WatchBeat(BaseModel):
    start: float
    end: float
    summary: str = Field(description="What happens in this beat, one sentence.")
    emotion: str = Field(description="The feeling, e.g. 'shock, humiliation'.")


class WatchMontage(BaseModel):
    start: float
    end: float
    description: str = Field(
        description="The wordless run: what it shows, its device (e.g. match cuts, same pose "
        "in a bigger world) and how it ends."
    )


class WatchShot(BaseModel):
    n: int = Field(description="The shot's number from <cuts>, unchanged.")
    start: float = Field(description="From <cuts>, unchanged.")
    end: float = Field(description="From <cuts>, unchanged.")
    framing: str = Field(description="Shot size and angle, e.g. 'close-up, low angle'.")
    camera: str = Field(description="Movement, e.g. 'static', 'push in', 'whip pan'.")
    on_screen: str = Field(
        description="Who and what is in frame: each person's look (age, hair, outfit), the "
        "place, key props."
    )
    action: str = Field(description="What happens in the shot.")
    emotion: str = Field(description="The faces and bodies, in words, e.g. 'groom stunned'.")
    live_action: bool = Field(
        description="True for real footage (a real person, phone video, a real room), even "
        "inside an animated reel, and for a morph into it."
    )
    text_on_screen: str = Field(
        description="Captions or text seen, described briefly so they can be ignored; '' if none."
    )


class WatchSpeaker(BaseModel):
    line: int = Field(description="The line's number from <transcript>.")
    speaker: str = Field(
        description="Who says it: one role name per person, the same all reel long ('groom', "
        "'bride'); 'narrator (V.O.)' for a voice nobody on screen speaks."
    )


class ReelWatch(BaseModel):
    logline: str = Field(description="One sentence: who, the turn, the payoff.")
    style: str = Field(
        description="The look as seen, in plain words and never a studio's or artist's name, "
        "e.g. '3D animated CG: rounded big-eyed characters, warm cinematic light'."
    )
    hook: WatchHook
    beats: list[WatchBeat] = Field(description="5–10 story beats in order, covering the reel.")
    montage: WatchMontage | None = Field(description="The run of quick wordless shots, or null.")
    shots: list[WatchShot] = Field(description="Exactly one per entry in <cuts>, in order.")
    speakers: list[WatchSpeaker] = Field(description="Exactly one per <transcript> line.")
    why_it_works: list[str] = Field(description="3–6 short reasons it holds a viewer.")


# --- The scene plan (flows 1b, P1): the script's words in scenes, before the breakdown ---


class PlanLine(BaseModel):
    line: int = Field(description="The script line's number, as in <script>.")
    action: str = Field(
        description="One vivid, exaggerated action we see while this line plays, in one "
        "sentence: 'He shakes and a fur blizzard fills the room'."
    )
    product: str | None = Field(
        description="★: the brand's product or screen id (product:N, screen:N) shown on this "
        "line, label or logo to camera; null when it isn't a key product moment."
    )


class PlanScene(BaseModel):
    id: int = Field(description="1, 2, 3, … in order.")
    part: str = Field(description="Its part of the structure: 'Problem', 'Proof'.")
    place: str = Field(description="One place and one time: 'INT. KITCHEN — NIGHT'.")
    cast: list[str] = Field(description="Who is in it: cast ids from the plan's cast only.")
    lines: list[PlanLine] = Field(description="Its script lines in order, one action each.")


class Structure(BaseModel):
    name: str = Field(description="The pattern's name ('Pet supplement'), or 'The reference reel'.")
    parts: list[str] = Field(description="The parts in order: ['Problem', 'Why', 'Payoff'].")
    based_on: Literal["reference", "pattern"] = Field(
        description="'reference' when it follows the <reference> or <study>, else 'pattern'."
    )
    lane: str = Field(
        default="",
        description="When the Style section lists lanes: the chosen lane's id, or '' for the "
        "look's default. Else ''.",
    )


class ScenePlan(BaseModel):
    """The plan as projects.plan stores it (data.md 1b), less the server's own fields."""

    structure: Structure
    cast: list[str] = Field(description="Cast ids from <cast>: the same in every scene.")
    scenes: list[PlanScene]


# --- The advisory check (flows 1b, P4): a still or a take against its sheets and product ---


class Finding(BaseModel):
    kind: Literal["face", "outfit", "product", "eyes", "screen", "cast"]
    who: str = Field(
        description="The reference's id from <references>: char:N or product:N. For eyes, the "
        "character's char:N, or '' if unclear; for screen, 'screen'; for cast, the missing "
        "person's char:N, or 'extra' for someone who shouldn't be there."
    )
    says: str = Field(
        description="One short line for the card: 'Mia's face may differ from her sheet'."
    )
    note: str = Field(
        description="The change note, ready to send: one plain instruction naming the reference "
        "and what it shows. Never a spoken line."
    )


class ItemCheck(BaseModel):
    """Advice only, never a pass or a fail: no findings means it matches the references."""

    findings: list[Finding] = Field(description="Only clear differences a viewer would notice.")


# --- The take watch (rule 11, Reed 3 Nov): every take looked at as it lands ---


class TakeFault(BaseModel):
    kind: Literal["style", "action", "motion", "cast", "product", "screen", "text", "lipsync",
                  "voice", "sound", "clipping", "timing"]  # fmt: skip
    at: float | None = Field(description="Where in the take, in seconds; null for all of it.")
    says: str = Field(description="One short line for the card: 'Eyes landed on the stomach'.")
    who: str = Field(
        default="",
        description="char:N or product:N from <references>, 'screen' or 'extra'; else ''.",
    )
    evidence: Literal["picture", "words", "measured", "sound"] = Field(
        description="What shows it: 'picture' (seen in the sampled frames), 'words' (only "
        "the transcript in <heard> suggests it), 'measured' (clipped samples in <measured>), "
        "'sound' (only the spectrogram, the loudness or a silence suggests it)."
    )


class TakeWatch(BaseModel):
    """One take, looked at: kept, or remade with its prompt rewritten for its model."""

    seen: str = Field(
        description="One or two plain sentences: what you saw, and what the transcript or the "
        "sound's picture suggests, said as a suggestion."
    )
    faults: list[TakeFault] = Field(max_length=6, description="Worst first; empty when it's good.")
    verdict: Literal["keep", "redo"]
    note: str = Field(default="", description="For redo: the change in a few plain words.")
    prompt: str = Field(default="", description="For redo: the whole clip prompt, rewritten.")


class NarrationMusic(BaseModel):
    """The instrumental bed under a narrated video (flows N1)."""

    prompt: str = Field(
        description="30 to 60 words for the music model: genre and mood, three to five "
        "instruments, the tempo, the turn by thirds, and 'Steady and low under the narration'. "
        "No artist, song or composer names; no vocals."
    )
    arc: str = Field(
        description="The mood in a few plain words: 'tense, then hopeful in the last third'."
    )


# --- Watch the cut (Reed, 1 Nov: "i want it to watch and make those fixes") ---


class CutFinding(BaseModel):
    clip_id: str = Field(description="The clip it's in, from <cut>: 'c3'.")
    start: float = Field(description="Where it starts, in cut seconds.")
    end: float = Field(description="Where it ends, in cut seconds.")
    says: str = Field(
        description="One plain line for the owner: \"c3: he says 'fogo', not 'fomo'\"."
    )
    kind: Literal["story", "picture", "cast", "text", "screen", "lipsync", "voice", "sound",
                  "words"] = Field(description="What kind of fault: in the picture or the story, "
                                   "lip-sync, the voice, other sound, or the words.")  # fmt: skip
    evidence: Literal["picture", "words", "measured", "sound"] = Field(
        description="What shows it: 'picture' (seen in the sampled frames), 'words' (only "
        "<transcript> suggests it), 'measured' (clipped samples in <measured>), 'sound' (only "
        "the spectrogram, the loudness or a silence suggests it)."
    )
    fix: Literal["redo", "pick", "mute", "keep"] = Field(
        description="The smallest fix that works: 'mute' an unscripted sound with nothing wrong "
        "in the picture; 'pick' another take of the clip; 'redo' the clip with a change note; "
        "'keep' a weakness no fix here would help."
    )
    take_id: int | None = Field(
        default=None, description="For pick: the id of one of that clip's other_takes; else null."
    )
    note: str = Field(
        default="",
        description="For redo, the change note, ready to send; for mute, what's heard there; "
        "for keep, why, for the owner.",
    )


class CutWatch(BaseModel):
    """The cut as a viewer meets it. Judging only: the director acts on it."""

    lands: bool = Field(description="Whether the ending lands.")
    summary: str = Field(description="One or two plain sentences on how it plays as a whole.")
    findings: list[CutFinding] = Field(
        max_length=6, description="Worst first, 6 at most; empty when it plays well."
    )


# --- The treatment (the Producer, 2 Nov): the director's first move, why the video holds ---


class Beat(BaseModel):
    id: str = Field(description="'b1', 'b2', … in order.")
    lines: list[int] = Field(description="The script line numbers this beat covers, in order.")
    purpose: str = Field(description="What it does for the story: hook, escalate, turn, payoff…")
    picture: str = Field(description="What we see: something happening, readable with no sound.")


class Treatment(BaseModel):
    hook: str = Field(description="The first 2 seconds: what we see and hear.")
    logline: str = Field(description="The story in one plain sentence.")
    why_it_holds: str = Field(description="Why a viewer of this look keeps watching.")
    beats: list[Beat] = Field(
        description="The video in order; together every line but the scene headings, once."
    )
    ending: str = Field(
        description="The payoff, and the call to action when the script has one, and why they land."
    )


# --- Review the stills (the Producer, 2 Nov): against the treatment, before any take ---


class StillFinding(BaseModel):
    shot_id: str = Field(description="The still's shot, from <frames>: '3.1'.")
    problem: str = Field(description="One plain line for the owner: what's wrong for the story.")
    note: str = Field(description="The change note for the redraw, ready to send.")


class StillsReview(BaseModel):
    ready: bool = Field(description="True when the stills tell the treatment and takes can start.")
    findings: list[StillFinding] = Field(
        max_length=8, description="Worst first; only what a viewer would notice; empty if ready."
    )


# --- The director (director-chat.md §5): one decision a turn, run by the server ---
# Anthropic's strict schemas allow 24 optional and 16 union-typed parameters in a whole request
# (a 400 past either). So every director field is required, and one that's often unused is
# sent as a plain string or integer: "" or 0 means none and reads as None here, so the server's
# code is unchanged. Only the few with a real "unchanged" (a time, an on/off) stay nullable.


def _all_required(schema: dict) -> None:
    """Every field required; no defaults (the answer gives each one, "" or 0 when unused)."""
    for prop in schema.get("properties", {}).values():
        prop.pop("default", None)
    schema["required"] = list(schema.get("properties", {}))


def _none(kind: dict):
    """A field sent as `kind` ("" or 0 for none, never null), read as None when empty."""
    return [WithJsonSchema(kind), BeforeValidator(lambda v: None if v == "" or v == 0 and
                                                  not isinstance(v, bool) else v)]  # fmt: skip


Name = Annotated[str | None, *_none({"type": "string"})]  # "": none
Id = Annotated[int | None, *_none({"type": "integer"})]  # 0: none


def _pick(*values: str):
    """One of `values`, or "" for none (read as None)."""
    return Annotated[Literal[values] | None, *_none({"type": "string", "enum": ["", *values]})]


class Strict(BaseModel):
    model_config = ConfigDict(json_schema_extra=_all_required)


class CutMove(Strict):
    """One free edit to the cut (the cut editor's own, app/cut_edits.py), for edit_cut."""

    kind: Literal["trim", "retime", "split", "swap", "presenter", "music", "undo"] = Field(
        description="retime: a piece's edges onto the words (tightens a dragging stretch); "
        "trim: a piece's start or end to a time (the last piece's end shortens or holds the "
        "ending); split: a piece in two at `at`; swap: a piece's B-roll for another take "
        "(`take_id`); presenter: `side`, `size` or `hidden` over a piece or start..end; "
        "music: `quieter_db` under the voice, `gaps`, or `removed`; undo: an edit (`edit_id`)."
    )
    piece: Name = Field(
        default=None, description="The piece from <video>.timeline.pieces, e.g. 'c7' or 'c7.12'."
    )
    start: float | None = Field(
        default=None, description="Seconds into the cut; null when the edit doesn't set it."
    )
    end: float | None = Field(
        default=None, description="Seconds into the cut; null when the edit doesn't set it."
    )
    at: float | None = Field(
        default=None, description="For split: seconds into the cut; else null."
    )
    take_id: Id = Field(default=None, description="For swap: a take's id; else 0.")
    side: _pick("left", "right") = None
    size: _pick("small", "medium", "large") = None
    hidden: bool | None = Field(
        default=None,
        description="For presenter: true hides it, false shows it again; null leaves it as it is.",
    )
    quieter_db: float | None = Field(
        default=None,
        description="For music: 0 to 30 dB under the voice (18 is 'a lot'; 0 stops it); null "
        "leaves it as it is.",
    )
    gaps: _pick("down", "rise") = Field(
        default=None, description="When no one speaks the music stays down, or rises."
    )
    removed: bool | None = Field(
        default=None,
        description="For music: true takes it out, false puts it back; null leaves it as it is.",
    )
    loop: bool | None = Field(
        default=None,
        description="For music: true loops it to fit the cut, false plays it once; null leaves it "
        "as it is.",
    )
    edit_id: Id = Field(default=None, description="For undo: from timeline.edits; else 0.")


class AskChoice(Strict):
    title: str = Field(description="The choice in a few words: 'He bins the pint'.")
    why: str = Field(description="One plain line: what it does for the story.")


class AskMove(Strict):
    """The `ask` tool's question (v6 S4-01, S4-02): one card in the chat."""

    kind: Literal["cast", "presenter", "voice", "place", "product", "brand_item", "story",
                  "question"] = Field(description="What it asks for.")  # fmt: skip
    topic: str = Field(default="", description="Two or three words for the bar: 'The husband'.")
    subject: str = Field(
        default="",
        description="The role, place, product or screen as the script names it ('husband'); "
        "always given for cast, presenter and place. A saved item of that name is used without "
        "asking.",
    )
    question: str = Field(default="", description="The question, plainly: 'Who plays the husband?'")
    why: str = Field(default="", description="One or two plain sentences: why it matters here.")
    describe: str = Field(
        default="", description="cast, presenter or place: what Generate options should draw."
    )
    choices: list[AskChoice] = Field(
        default=[], description="story: two to four choices, in order (A, B, …)."
    )
    pick: Name = Field(
        default=None,
        description="Your pick: a story choice's letter, or the saved item's name you'd use.",
    )
    ask_id: Id = Field(
        default=None, description="Only to close an open question no longer needed; else 0."
    )


class LookMove(Strict):
    name: str = Field(description="The place or character as people call it ('The penthouse').")
    description: str = Field(
        default="",
        description="For add_place: what the place looks like, in a sentence, from the plan and "
        "the treatment (the light, the time of day, what's in it). Else empty.",
    )
    shot_ids: list[str] = Field(
        default_factory=list,
        description="For add_place: the plan's shots that happen there, e.g. ['3.1', '3.2'].",
    )
    library_item_id: Id = Field(
        default=None,
        description="For add_place: the place to use (a place card's answer: the brand's saved "
        "one, or the one made for this video from its photo), by its id; 0 makes a new one "
        "for this video from `description`.",
    )


class DirectorTurn(Strict):
    tool: Literal[
        "treatment", "plan", "make_looks", "storyboard", "stills", "review_stills",
        "redraw_still", "clip_prompts", "make_take", "pick_take", "final_cut", "watch_cut",
        "mute", "splice_word", "add_sound", "song", "narration", "host", "edit_cut", "ask",
        "add_place", "change_look", "ask_cast_ok", "wait", "deliver", "stop", "clip_model",
        "settings", "split_clip",
    ] = Field(
        description="The one action to take now. 'wait' only while something it started is "
        "still being made or waits for the owner; 'deliver' when the cut is made and good; "
        "'stop' when it can't go on (the 'why' says what and why)."
    )  # fmt: skip
    clip_id: Name = Field(
        default=None,
        description="For make_take, pick_take, mute, splice_word, add_sound, clip_model and "
        "split_clip: the clip, e.g. 'c3'. For make_take, empty makes a first take of every clip "
        "that has none; for "
        "add_sound, empty adds sound to every silent take in the cut. Else empty.",
    )
    take_id: Id = Field(
        default=None,
        description="For pick_take: the take's id (not its number). For song or narration "
        "with no note: the take to use. Else 0.",
    )
    shot_id: Name = Field(
        default=None, description="For redraw_still: the still's shot, e.g. '3.1'; else empty."
    )
    voice: _pick(
        "Sarah", "Alexandra", "Hope", "Jane", "Austin", "Roger", "English_FriendlyPerson",
        "English_Trustworth_Man", "English_Upbeat_Woman", "English_ConfidentWoman",
        "English_Graceful_Lady",
    ) = Field(
        default=None,
        description="For narration being made: the narrator's voice. A person's pick or the "
        "video's own voice (its presenter's, else its style's, e.g. Dr. Pickle's) is kept "
        "whatever this says. Empty keeps the voice in use on a remake, else gives Sarah (a UGC "
        "presenter in one spot, talks or corner: English_FriendlyPerson). Else empty.",
    )  # fmt: skip
    emotion: _pick(
        "auto", "happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm", "fluent",
        "neutral",
    ) = Field(
        default=None,
        description="For narration in an English_ voice (MiniMax): the delivery's emotion; empty "
        "or 'auto' lets the voice choose from the words. Its speed follows: an emotion reads "
        "slower, so the speed rises to keep the style's pace, and a remake in the same emotion "
        "is set from the last read's measured pace (the take's 'pace' against 'pace_wanted'). "
        "Else empty.",
    )  # fmt: skip
    reading: str = Field(
        default="",
        description="For narration in an English_ voice, optional: the narration's words exactly "
        "as the script has them, with only pause marks between words, e.g. <#0.3#> (0.2-0.5 s, "
        "never two in a row), and a few sounds a person makes, e.g. (breath), (chuckle), "
        "(sighs), where they'd really happen; a changed word is refused. Else empty.",
    )
    model: Name = Field(
        default=None,
        description="For clip_model: the catalogue id of the model that makes this clip "
        '(Reed, 6 Nov: "Omni is more for the realistic stuff"), the reason in `why`. UGC\'s '
        "clips stay on 'gemini-omni-1.2' (its B-roll, and a talker who acts in the story); a "
        "talker in one spot is HeyGen in our own voice and never moves. An animated style's "
        "clips are on its Seedance, and 'gemini-omni-1.2' may make a realistic shot there. Empty "
        "puts the clip back on the video's model. For settings with setting video_model or "
        "image_model: the model's id, empty for Auto. Else empty.",
    )
    setting: _pick("look", "video_model", "image_model", "aspect_ratio", "presenter") = Field(
        default=None,
        description="For settings: which of the video's settings to switch, when a person asks "
        "in the chat or the treatment chose it: look (the style), video_model, image_model, "
        "aspect_ratio (the shape) or presenter (how the presenter appears: talks, corner or "
        "acts). A setting a person chose themselves stays theirs. Else empty.",
    )  # fmt: skip
    value: Name = Field(
        default=None,
        description="For settings with setting look, aspect_ratio or presenter: the new value "
        "(a style id, '9:16', or talks / corner / acts); empty for the style's own. Else empty.",
    )
    look: LookMove | None = Field(
        default=None,
        description="For add_place: the place, its look in words and the plan's shots there. "
        "For change_look: the character or place by name (as <video>'s cast_ok names it), "
        "with the change in `note`. Else null.",
    )
    word: Name = Field(
        default=None,
        description="For splice_word: the brand word as the script spells it, e.g. 'fomo', from "
        "that clip's can_splice; else empty.",
    )
    note: str = Field(
        default="",
        description="What it must change, in plain words: for make_take as a redo, what to fix "
        "(e.g. 'say fomo as FOH-moh; no extra people'); for redraw_still, what the beat needs "
        "in the frame; for treatment or plan made again, what changes; for song with no style "
        "yet, the style line ('laid-back breezy pop, warm female vocal, 100 BPM, acoustic "
        "guitar, sunny, modern polished'); for song made again, the music's change ('vocals "
        "start immediately, no instrumental intro'); for narration "
        "made again, the voice's change ('slower and warmer'); for host with a UGC talker, the "
        "talker's motion, written for this narration's emotion and lines: what the face, head "
        "and hands do and what's in front of them, never a gesture the place can't hold ('close "
        "to tears, fighting it: chin trembles, lips pressed between phrases, a glance down and "
        "back; both hands stay on the steering wheel'); for add_sound, the sounds "
        "asked for and how much, in the person's words ('slight sound effects'); else empty.",
    )
    edit: CutMove | None = Field(
        default=None, description="For edit_cut: the one edit (free). Else null."
    )
    ask: AskMove | None = Field(default=None, description="For ask: the question; else null.")
    why: str = Field(
        description="One short plain sentence: why this action now, logged on the video. On "
        "'deliver', one short sentence; the note is `made`, `unsure` and `needs`. On 'stop', "
        "what the owner needs to know; on 'ask' with ask_id, why it's no longer needed."
    )
    made: str = Field(
        default="",
        description="On 'deliver' only: the delivery note's 'What I made', one short paragraph: "
        "its length, who's in it, the scenes and clips, and how it opens; never "
        "the changes, timecodes or cost (the server adds those). Else empty.",
    )
    unsure: str = Field(
        default="",
        description="On 'deliver' only: 'What remains uncertain': every problem not resolved "
        "and every check that didn't run or failed, plainly; empty only when there's none.",
    )
    needs: str = Field(
        default="",
        description="On 'deliver' only: 'What I need from you': what the owner must decide or "
        "approve; empty only when nothing is open.",
    )
