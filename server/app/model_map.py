"""Reed's model map (4 Nov): which model makes what, and what each needs sent. A presenter
talker is HeyGen Avatar IV from a still with our MiniMax voice; B-roll is Seedance, silent, with
sound effects added where they help. Photoreal Seedance B-roll (rule 10's exception, Reed, 4
Nov) describes the person from their approved character description, in the same words in
every prompt (clip_takes._in_words), instead of attaching their photo or an opening still with
them in it; products and screens stay attached. Why: in th-20s
(.context/tests/th-20s/REPORT.md) every Seedance 2.0 take sent a photoreal teenager's photo was
refused ("sensitive", E005) and 1 Lite refused it as invalid input (E006), not charged. That
test doesn't show every photoreal reference is refused, and words don't guarantee the person
looks the same in every shot. HeyGen, Omni and stylised characters keep their references."""

from app import looks

PHOTOREAL = ("ugc",)  # styles whose people are photoreal (a real person filmed on a phone)


def unsent(look: str | None, model_id: str, shots: list[dict]) -> tuple[str, ...]:
    """The references a take leaves out and describes in words instead: in a photoreal style
    on Seedance, every character sheet, and the opening still when someone is in it."""
    if not model_id.startswith("seedance") or looks.base(look or looks.DEFAULT) not in PHOTOREAL:
        return ()
    people = any(s.get("character_ids") for s in shots)
    return ("char:", "frame:") if people else ("char:",)
