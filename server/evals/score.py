"""Score saved Claude answers against the eval cases. No calls are made here.

Usage (from server/): python -m evals.score <outputs dir> [prompt version label]
The outputs dir holds `<case>.<step>.json` (each step's structured answer) and, for cases with a
breakdown, `<case>.script.txt` (the working script the breakdown was given)."""

import json
import re
import sys
from pathlib import Path

from app.catalogue import get_model
from app.prompts import SCHEMAS, check, required

CASES = json.loads((Path(__file__).parent / "cases.json").read_text())


def score(out: Path, case: dict) -> list[str]:
    brand = CASES["brands"][case["brand"]]
    screens = required(brand["screens"], brand.get("product"))
    video = get_model("seedance-2.5")
    exp, problems, answers = case["expect"], [], {}
    for step in case["steps"]:
        path = out / f"{case['id']}.{step}.json"
        if not path.exists():
            return [f"missing {path.name}"]
        answers[step] = SCHEMAS[step].model_validate_json(path.read_text())
    script = "\n".join(case["script"] or [])

    if e := answers.get("enhance"):
        problems += check.enhance(script, e, screens)
        marks = {}
        for s in e.suggestions:
            marks.setdefault(s.anchor.line, []).append(s)
        for n, word in exp.get("notes_mention", {}).items():
            if not any(x.line == int(n) and word in x.text.lower() for x in e.notes):
                problems.append(f"expected a note on line {n} that mentions '{word}'")
        for n, sid in exp.get("screens_at", {}).items():
            if not any(s.screen_id == sid for s in marks.get(int(n), [])):
                problems.append(f"expected {sid} at line {n}")
        if len(e.suggestions) > exp.get("max_suggestions", 99):
            problems.append(
                f"{len(e.suggestions)} suggestions, expected at most {exp['max_suggestions']}"
            )
        if (sid := exp.get("screen_anywhere")) and sid not in {s.screen_id for s in e.suggestions}:
            problems.append(f"expected {sid} somewhere")
        for word in exp.get("notes_absent", []):
            if any(word in note.text.lower() for note in e.notes):
                problems.append(f"a note mentions '{word}', which this case shouldn't need")

    if d := answers.get("script_draft"):
        lo, hi = exp["drafts"]
        if not lo <= len(d.drafts) <= hi:
            problems.append(f"{len(d.drafts)} drafts, expected {lo}–{hi}")
        lo, hi = exp["words_per_draft"]
        ref_lines = []
        if exp.get("reference_words"):
            path = Path(__file__).parents[2] / case["reference"]["path"]
            ref_lines = list(
                dict.fromkeys(x["text"] for x in json.loads(path.read_text())["lines"])
            )
        for i, draft in enumerate(d.drafts, 1):
            spoken = re.findall(r"^[A-Z][A-Z .'()-]*:\s*(.*)$", draft.script, re.M)
            words = len(" ".join(spoken).split())
            if not lo <= words <= hi:
                problems.append(f"draft {i}: {words} spoken words, expected {lo}–{hi}")
            problems += [f"draft {i}: {p}" for p in check.reference_lines(
                draft.script, ref_lines, case.get("new_lines", False))]  # fmt: skip
            if (end := exp.get("end_line")) and end not in draft.script:
                problems.append(f"draft {i}: doesn't end on the brand's end line")

    if bd := answers.get("breakdown"):
        working = out / f"{case['id']}.script.txt"
        script = working.read_text() if working.exists() else script
        problems += check.breakdown(script, bd, screens, video.duration.min, video.duration.max)
        if "clips" in exp and not exp["clips"][0] <= len(bd.clips) <= exp["clips"][1]:
            problems.append(f"{len(bd.clips)} clips, expected {exp['clips']}")
        shots = [shot for scene in bd.scenes for shot in scene.shots]
        for n, sid in exp.get("screen_lines", {}).items():
            if not any(int(n) in s.script_lines and sid in s.screen_ids for s in shots):
                problems.append(f"expected {sid} in the shot for line {n}")
        opening = " | ".join(s.line or "" for s in shots[:3])
        problems += [f"the opening shots don't say “{x}”"
                     for x in exp.get("opening_lines", []) if x not in opening]  # fmt: skip
        screen_shots = sum(1 for s in shots if s.screen_ids)
        if screen_shots < exp.get("min_screen_shots", 0):
            problems.append(
                f"{screen_shots} shots show a screen, expected {exp['min_screen_shots']}+"
            )
        if cp := answers.get("clip_prompts"):
            limits = video.max_reference_images, video.max_reference_audios
            problems += check.clip_prompts(bd, cp, *limits)
            shown = " ".join(check.QUOTED.sub("", c.prompt) for c in cp.clips).lower()
            problems += [f"clip prompts say '{w}' outside the dialogue"
                         for w in exp.get("clip_absent", []) if w in shown]  # fmt: skip
            problems += [f"clip prompts never say '{w}'"
                         for w in exp.get("clip_present", []) if w not in shown]  # fmt: skip
    if v := answers.get("variations"):
        never = brand["brand"].get("never_say", []) + case.get("never_say", [])
        names = [c.split(" ", 1)[1].split(",")[0].split(" (")[0] for c in case["cast"]]
        end = brand["brand"].get("end_line", "")
        problems += check.variations(script, v, screens, end, never, case["count"], names)
    if cs := answers.get("cast_slots"):
        made = answers.get("variations")
        versions = (
            {0: script} | {i: x.script for i, x in enumerate(made.variations, 1)}
            if made
            else {0: script}
        )
        names = [c.split(" ", 1)[1].split(",")[0].split(" (")[0] for c in case["cast"]]
        problems += check.cast_slots(versions, cs, names)
        roles = " | ".join(s.role for s in cs.slots).lower()
        problems += [
            f"no slot for {n}" for n in exp.get("slots_named", []) if n.lower() not in roles
        ]
        if (any_ := exp.get("slot_any")) and not any(w in roles for w in any_):
            problems.append(f"no slot matching any of {any_}")
        problems += [f"a slot for '{w}'" for w in exp.get("slots_absent", []) if w in roles]
    saved = " ".join(a.model_dump_json() for a in answers.values()).lower()
    problems += [
        f"copies '{w}' from the reference" for w in exp.get("forbid", []) if w.lower() in saved
    ]
    return problems


def main(out: Path, label: str = "") -> int:
    failed = 0
    print(f"# Eval {label}".strip())
    for case in CASES["cases"]:
        problems = score(out, case)
        failed += bool(problems)
        print(f"{'FAIL' if problems else 'ok  '} {case['id']}")
        for p in problems:
            print(f"     - {p}")
    print("Now read each answer against its case's 'good' list: checks can't judge engagement.")
    return failed


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), *sys.argv[2:3]))
