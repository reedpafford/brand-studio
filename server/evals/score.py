"""Score saved Claude answers against the eval cases. No calls are made here.

Usage (from server/): python -m evals.score <outputs dir> [prompt version label]
The outputs dir holds `<case>.<step>.json` (each step's structured answer) and, for cases with a
breakdown, `<case>.script.txt` (the working script the breakdown was given)."""

import json
import re
import sys
from pathlib import Path

from app.catalogue import get_model
from app.prompts import SCHEMAS, check, required, schemas

CASES = json.loads((Path(__file__).parent / "cases.json").read_text())
ROOT = Path(__file__).parents[2]


def reel_inputs(case: dict) -> tuple[list[dict], list[dict] | None]:
    """An import case's transcript and cut list, as prep gives them: from a gold BREAKDOWN.json
    or written in the case (cuts None until prep has run on the video)."""
    reel = case["reel"]
    if gold := reel.get("gold"):
        bd = json.loads((ROOT / gold).read_text())
        cuts = [{k: s[k] for k in ("n", "start", "end")} for s in bd["shots"]]
        return [{k: x[k] for k in ("start", "end", "text")} for x in bd["lines"]], cuts
    return reel["transcript"], reel["cuts"]


def kept_lines(watch, transcript: list[dict]) -> tuple[list[str], list[str]]:
    """The reel's lines and speakers outside its live-action shots (those are dropped)."""
    live = [s for s in watch.shots if s.live_action]
    who = {s.line: s.speaker for s in watch.speakers}
    kept = [(x["text"], who.get(n, "")) for n, x in enumerate(transcript, 1)
            if not any(s.start <= x["start"] < s.end for s in live)]  # fmt: skip
    return list(dict.fromkeys(t for t, _ in kept)), [w for _, w in kept]


def reference_montage(ref: dict) -> str:
    """What a reference's montage shows (a BREAKDOWN.json or a reel reading, as a dict)."""
    if not (m := ref.get("montage")):
        return ""
    shots = [s for s in ref["shots"] if m["start"] <= s["start"] < m["end"]]
    return " ".join([m["description"]] + [f"{s['on_screen']} {s['action']}" for s in shots])


def score(out: Path, case: dict) -> list[str]:
    brand = CASES["brands"][case["brand"]]
    screens = required(brand["screens"], brand.get("product"))
    video = get_model("seedance-2.5")
    exp, problems, answers = case["expect"], [], {}
    for step in case["steps"]:
        path = out / f"{case['id']}.{step}.json"
        if not path.exists():
            return [f"missing {path.name}"]
        answers[step] = SCHEMAS.get(step, schemas.ReelWatch).model_validate_json(path.read_text())
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

    ref_lines, speakers, ref_montage = [], None, ""
    if ref := case.get("reference"):
        ref_montage = reference_montage(json.loads((ROOT / ref["path"]).read_text()))
    if w := answers.get("reel_watch"):
        transcript, cuts = reel_inputs(case)
        cuts = cuts or [{"n": s.n, "start": s.start, "end": s.end} for s in w.shots]
        ex, found = exp["watch"], check.reel_watch(w, cuts, transcript)
        for line in ex.get("live_lines", []):
            said = f"{check.ADVICE}“{line}” is in a live-action shot, so it's dropped"
            if said in found:
                found.remove(said)
            else:
                found.append(f"“{line}” isn't in a live-action shot")
        problems += found
        if (n := ex.get("shots")) and len(w.shots) != n:
            problems.append(f"{len(w.shots)} shots, expected {n}")
        live = [s.n for s in w.shots if s.live_action]
        if "live_shots" in ex and live != ex["live_shots"]:
            problems.append(f"live-action shots {live}, expected {ex['live_shots']}")
        roles = sorted({check.role_key(s.speaker) for s in w.speakers})
        if "speakers" in ex and roles != sorted(ex["speakers"]):
            problems.append(f"speakers {roles}, expected {sorted(ex['speakers'])}")
        if (lo_hi := ex.get("speaker_count")) and not lo_hi[0] <= len(roles) <= lo_hi[1]:
            problems.append(f"{len(roles)} speakers ({', '.join(roles)}), expected {lo_hi}")
        problems += [f"the hook doesn't mention '{x}'" for x in ex.get("hook_mentions", [])
                     if x not in w.hook.mechanic.lower()]  # fmt: skip
        ref_lines, speakers = kept_lines(w, transcript)
        ref_montage = reference_montage(w.model_dump())

    if d := answers.get("script_draft"):
        lo, hi = exp["drafts"]
        if not lo <= len(d.drafts) <= hi:
            problems.append(f"{len(d.drafts)} drafts, expected {lo}–{hi}")
        lo, hi = exp["words_per_draft"]
        if exp.get("reference_words") and speakers is None:
            path = Path(__file__).parents[2] / case["reference"]["path"]
            ref_lines = list(
                dict.fromkeys(x["text"] for x in json.loads(path.read_text())["lines"])
            )
        for i, draft in enumerate(d.drafts, 1):
            spoken = re.findall(r"^[A-Z][A-Z .'()-]*:\s*(.*)$", draft.script, re.M)
            words = len(" ".join(spoken).split())
            if not lo <= words <= hi:
                problems.append(f"draft {i}: {words} spoken words, expected {lo}–{hi}")
            problems += [f"draft {i}: {p}" for p in check.echo_lines(draft.script)]
            problems += [f"draft {i}: {p}" for p in check.repeated_payoffs(
                check.montage_text(draft.script), ref_montage, "the reference's")]  # fmt: skip
            problems += [f"draft {i}: {p}" for p in check.reference_lines(
                draft.script, ref_lines, case.get("new_lines", False))]  # fmt: skip
            if speakers is not None:
                names = [c.split(" ", 1)[1].split(",")[0] for c in case["cast"]]
                problems += [f"draft {i}: {p}" for p in check.reel_speakers(
                    draft.script, speakers, names, exp.get("end_line", ""))]  # fmt: skip
            if (end := exp.get("end_line")) and end not in draft.script:
                problems.append(f"draft {i}: doesn't end on the brand's end line")

    if bd := answers.get("breakdown"):
        working = out / f"{case['id']}.script.txt"
        script = working.read_text() if working.exists() else script
        problems += check.breakdown(script, bd, screens, video.duration.min, video.duration.max)
        if "clips" in exp and not exp["clips"][0] <= len(bd.clips) <= exp["clips"][1]:
            problems.append(f"{len(bd.clips)} clips, expected {exp['clips']}")
        shots = [shot for scene in bd.scenes for shot in scene.shots]
        end = brand["brand"].get("end_line", "")
        problems += check.cta_screen(shots, end, brand["brand"]["name"])
        lines = script.splitlines()
        in_montage = {n for n, x in enumerate(lines, 1) if "montage" in x.lower()}
        montage = " ".join(s.action for s in shots if in_montage & set(s.script_lines))
        if "script_draft" in answers:  # an editor's own script may keep its payoffs
            problems += check.repeated_payoffs(montage, ref_montage, "the reference's")
        for n, sid in exp.get("screen_lines", {}).items():
            if not any(int(n) in s.script_lines and sid in s.screen_ids for s in shots):
                problems.append(f"expected {sid} in the shot for line {n}")
        opening = " | ".join(s.line or "" for s in shots[:3])
        problems += [f"the opening shots don't say “{x}”"
                     for x in exp.get("opening_lines", []) if x not in opening]  # fmt: skip
        figures = sum(1 for s in shots if check._money(s) and check.MONEY.search(s.action))
        if figures < exp.get("min_money_figures", 0):
            problems.append(f"{figures} trading shots say what they read, expected "
                            f"{exp['min_money_figures']}+")  # fmt: skip
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
        for i, x in enumerate(v.variations, 1):
            problems += [f"variation {i}: {p}" for p in check.echo_lines(x.script)]
            again = check.repeated_payoffs(
                check.montage_text(x.script), check.montage_text(script), "the original's"
            )
            problems += [f"variation {i}: {p}" for p in again]
    if cs := answers.get("cast_slots"):
        made = answers.get("variations")
        script = answers["script_draft"].drafts[0].script if "script_draft" in answers else script
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
    saved = " ".join(a.model_dump_json() for k, a in answers.items() if k != "reel_watch").lower()
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
