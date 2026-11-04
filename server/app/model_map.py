"""Reed's model map (4 Nov): which model makes what, and what each needs sent. A presenter
talker is HeyGen Avatar IV from a still with our MiniMax voice; B-roll is Seedance, silent, with
sound effects added where they help. Seedance refuses a photoreal person's picture (th-20s,
.context/tests/th-20s/REPORT.md: every Seedance 2.0 clip with the photo of the teenage daughter
was refused as "sensitive", E005, and 1 Lite refused it as invalid input, E006; not charged),
so in a photoreal style its takes never get a person's picture: the person is said in the same
words in every prompt instead (the sheet's description, clip_takes._in_words), which kept her
the same girl in every shot."""

from app import looks

PHOTOREAL = ("ugc",)  # styles whose people are photoreal (a real person filmed on a phone)


def unsent(look: str | None, model_id: str, shots: list[dict]) -> tuple[str, ...]:
    """The references a take leaves out and says in words: in a photoreal style on Seedance,
    every character sheet, and the opening still when someone is in it."""
    if not model_id.startswith("seedance") or looks.base(look or looks.DEFAULT) not in PHOTOREAL:
        return ()
    people = any(s.get("character_ids") for s in shots)
    return ("char:", "frame:") if people else ("char:",)
