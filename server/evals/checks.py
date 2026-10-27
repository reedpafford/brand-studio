"""Checks only the evals score (moved out of the app, rule 26): the app never runs them, and
their advice would have no one-click fix there (rule 22)."""

import re

from app.prompts.check import ADVICE, _words

SPOKEN = re.compile(r'\b([A-Z][\w-]*(?: [A-Z][\w-]*)?) \(([^)"]*)\):\s*["“]')  # Nate (…): "


def unlabelled(prompt: str) -> list[str]:
    """Advice when a spoken line doesn't name its language: without "in English" Seedance may
    speak another one (Reed, a Change this… take, 2026-10-27; docs/prompting/seedance-2.5.md §3).
    Scored in the evals only: in the app the server adds "Use English: …" to every take, and a
    flag on every saved clip would have no one-click fix (Current rules 22)."""
    who = [m.group(1) for m in SPOKEN.finditer(prompt) if "in english" not in m.group(2).lower()]
    if not who:
        return []
    names = ", ".join(dict.fromkeys(who))
    return [f"{ADVICE}{names}: say each spoken line's language, e.g. {who[0]} (in English, …)"]


VO_LINE = re.compile(r"^([A-Z][A-Z .'-]*?) \((?:V\.O\.|VO|voice-over)\):\s*(.*)$", re.I)
SAID_LINE = re.compile(r"^([A-Z][A-Z .'-]*?)(?: \([^)]*\))?:\s*(.*)$")


def echo_lines(script: str) -> list[str]:
    """An echo (a V.O. from a character who also speaks on screen) repeats something they said
    earlier, so the callback lands (Reed, live test 2026-10-26). Advice naming the closest
    earlier line. A narrator heard only in V.O. is never an echo."""
    problems, said = [], {}
    for line in (x.strip() for x in script.splitlines()):
        if (m := VO_LINE.match(line)) and m.group(1).upper() in said:
            words, earlier = _words(m.group(2)), said[m.group(1).upper()]
            if words and not any(words in _words(e) for e in earlier):
                best = max(earlier, key=lambda e: len(set(words.split()) & set(_words(e).split())))
                problems.append(
                    f"{ADVICE}the echo “{m.group(2)}” calls back to nothing "
                    f"{m.group(1).title()} said; repeat “{best}”"
                )
        elif (m := SAID_LINE.match(line)) and not VO_LINE.match(line):
            said.setdefault(m.group(1).upper(), []).append(m.group(2))
    return problems


PAYOFFS = {  # the got-rich run copied too often (Reed, 2026-10-27): one example among many
    "keys": r"\bkeys\b",
    "a car": r"\b(?:car|coupe|supercar|sports car|suv|lamborghini|lambo|ferrari|porsche)\b"
    r"|behind the wheel",
    "a penthouse": r"\bpenthouse\b",
    "a balcony": r"\b(?:balcony|terrace)\b",
    "a skyline": r"\bskyline\b",
    "a mansion": r"\b(?:mansion|villa)\b",
    "a yacht": r"\byacht\b",
    "a private jet": r"\bprivate jet\b",
}


def payoffs(text: str) -> list[str]:
    """The stock payoffs a montage shows, in the order it first shows them."""
    found = [(m.start(), name) for name, pat in PAYOFFS.items()
             if (m := re.search(pat, text, re.I))]  # fmt: skip
    return [name for _, name in sorted(found)]


def montage_text(script: str) -> str:
    """A script's montage action lines (the house format names them "Wordless montage, …")."""
    return " ".join(x for x in script.splitlines() if "montage" in x.lower())


def repeated_payoffs(mine: str, earlier: str, whose: str) -> list[str]:
    """Advice when a montage shows two or more of the stock payoffs an earlier one showed (the
    reference's or the original's): each video invents its own."""
    same = [x for x in payoffs(mine) if x in payoffs(earlier)]
    if len(same) < 2:
        return []
    return [f"{ADVICE}the montage repeats {whose} payoffs ({', '.join(same)}); invent ones "
            "that fit this story and its people"]  # fmt: skip
