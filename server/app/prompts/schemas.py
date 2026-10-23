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
        "brand_screen: the screen line ('★ fomo screen: Token chart up — on Leo's phone, fills "
        "the frame')."
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


class ScriptDrafts(BaseModel):
    drafts: list[ScriptDraft] = Field(
        description="2 or 3 drafts, each with a clearly different hook; the story after the "
        "hook may stay the same."
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
        description="Who reacts and how, readable at phone size (eyes snap wide, jaw drops), "
        "or null."
    )
    camera: str = Field(
        description="Size, angle and move, e.g. 'Low-angle close-up, fast push-in' or 'Macro "
        "insert of the phone screen, static'."
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
        description="Why the clip ends here: a hard cut that changes place or time, or the "
        "model's length limit. 'end' for the last clip."
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


# --- Quick clip: Improve prompt ---


class ImprovedPrompt(BaseModel):
    prompt: str = Field(description="The video prompt, in the shape the system prompt shows.")
