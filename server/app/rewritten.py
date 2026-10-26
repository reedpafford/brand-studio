""" "Was:" marks on a reel-made script (reel-import.md §6): which lines the writer rewrote for the
brand swap, and the reel's original words for each. They follow the lines through edits, so an
edited marked line keeps its mark, until the version is approved."""

import difflib

from app.cast_roles import LABEL


def spoken(line: str) -> str | None:
    """The words of a dialogue line ("NATE (V.O.): Hi." -> "Hi."), or None for other lines."""
    label = LABEL.match(line)
    return line[label.end() :].strip() if label else None


def marks(text: str, changed: list[str], reel_lines: list[str]) -> list[dict]:
    """[{line_index, was}] for each line the writer says it rewrote, paired with the reel line
    it took the place of (by lining up the kept lines; a rewrite sits where its original was)."""
    lines = text.splitlines()
    said = [(i, s) for i, line in enumerate(lines) if (s := spoken(line)) is not None]
    want = {" ".join(c.split()) for c in changed}
    words = [" ".join(s.split()) for _, s in said]
    reel = [" ".join(x.split()) for x in reel_lines]
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, reel, words, autojunk=False
    ).get_opcodes():
        if tag not in ("replace", "insert"):
            continue
        for k in range(j1, j2):
            if words[k] not in want:
                continue
            was = reel[min(i1 + (k - j1), i2 - 1)] if i2 > i1 else ""
            out.append({"line_index": said[k][0], "was": was})
    return out


def follow(old_text: str, new_text: str, items: list[dict]) -> list[dict]:
    """The marks moved to where their lines are after an edit: lines kept stay with their
    text; an edited line keeps its mark in place; a deleted line loses it."""
    old, new = old_text.splitlines(), new_text.splitlines()
    where = {}
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, old, new, autojunk=False
    ).get_opcodes():
        if tag == "equal" or tag == "replace":
            for k in range(i1, i2):
                if k - i1 < j2 - j1:
                    where[k] = j1 + (k - i1)
    return [{**m, "line_index": where[m["line_index"]]} for m in items if m["line_index"] in where]
