"""Output schemas for each Claude step. Claude reads the field descriptions, so they are part
of the prompt. No numeric or length constraints here: structured outputs ignore them, so limits
are stated in the descriptions and checked in `check.py`.

Asset ids are strings with a kind prefix, as listed in the brand block and the user message:
`screen:12`, `char:5`, `place:3`, `prop:7`, `frame:c2`."""

from typing import Literal

from pydantic import BaseModel, Field

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


class Shot(BaseModel):
    id: str = Field(description="'<scene>.<shot>', e.g. '1.1', '1.2', '2.1'.")
    script_lines: list[int] = Field(description="Numbered script lines this shot covers.")
    speaker: str | None = Field(description="Who speaks in this shot (cast name), or null.")
    line: str | None = Field(
        description="The exact spoken words from the script, unchanged; null if nobody speaks. "
        "One speaker's line per shot."
    )
    action: str = Field(description="What we see happen, concretely, in one sentence.")
    reaction: str | None = Field(
        description="Who reacts, the feeling and its reason, then how it shows at phone size, "
        "e.g. 'Tasha, touched he remembered her: eyes well, a shaky smile'; or null."
    )
    camera: str = Field(
        description="Size, angle and move, e.g. 'Low-angle close-up, fast push-in' or "
        "'Over-the-shoulder close-up on the phone in his hand, static'."
    )
    seconds: float = Field(
        description="Estimated length. Dialogue: words / 4.8 plus any held reaction. Silent "
        "reactions and inserts: 0.5–1.5."
    )
    character_ids: list[str] = Field(description="Cast ids on screen in this shot.")
    place_id: str | None = Field(description="Place id from the user message, or null.")
    moment: str | None = Field(
        description="The brand moment this shot is, from the brand block's moments (e.g. "
        "'trading', 'win', 'loss'), or null."
    )
    screen_ids: list[str] = Field(
        description="Brand screens (screen:N) and the project's product (product:N) shown in "
        "this shot. Required whenever `moment` is one the brand block lists them for."
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
    style: str = Field(description="The look, e.g. '3D animated (Pixar-style CG)'.")
    hook: WatchHook
    beats: list[WatchBeat] = Field(description="5–10 story beats in order, covering the reel.")
    montage: WatchMontage | None = Field(description="The run of quick wordless shots, or null.")
    shots: list[WatchShot] = Field(description="Exactly one per entry in <cuts>, in order.")
    speakers: list[WatchSpeaker] = Field(description="Exactly one per <transcript> line.")
    why_it_works: list[str] = Field(description="3–6 short reasons it holds a viewer.")
