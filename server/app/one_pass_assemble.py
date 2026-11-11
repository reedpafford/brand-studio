"""The one-pass director's plan as rows, built in code with no model call (app/one_pass.py).
`to_breakdown` turns the plan's clips into scenes, shots and clips, each spoken line's words
put in from the script by its number, never re-typed (rule 19). `assemble` writes each clip's
prompt from the plan: it keeps the house line names (Audio, References, Summary, Style,
Setting, Shot, Keep), so the free repairs and checks every clip goes through read it, but each
line carries only what the plan gives. The reference pictures carry how people, places and
products look and the style's `clip_style` the look, so nothing describes a face or restates
the style. Pictures are attached by the same rules as any clip (`clip_prompts.with_cast`:
rules 10, 13, 14 and 16), which also writes their References and Keep words."""

import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clip_prompts, guides, looks, model_map, one_pass_timed, prompts
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.prompts import check
from app.prompts.schemas import (
    Breakdown,
    Clip,
    ClipPrompt,
    FootageUse,
    Reference,
    Scene,
    ShootingPlan,
    Shot,
)

PLAN = "shooting_plan"  # in a breakdown's data: the director's plan it was built from
# The house audio lines (app/prompts/clip_prompts.md), with the clip's own sound in them. The
# list of other words for music stays: it stopped Seedance scoring clips on its own, and music
# is added in post. Omni's take swaps both lines for its own short Sound line.
NO_MUSIC = ("No music, background music, BGM, score, instrumental, melody, synth effects, "
            "ambient pad, drone, swelling tone or stinger. No subtitles.")  # fmt: skip
SPOKEN = "Audio: only the spoken lines and {}. " + NO_MUSIC
SILENT = check.SILENT + "{}. " + NO_MUSIC
REAL = "[Image{}] is the real {}; show it exactly as it is."  # rules 13 and 16, as `with_cast`
PLACE = "[Image{}] is the place, {}."
TOO_LONG = "its prompt is {n:,} characters, over the {most:,} {model} takes"
OFF = re.compile(r"\s*\(.*?\)")  # a speaker's "(V.O.)": never part of their name


def spoken(text: str, talker: str = "") -> dict[int, tuple[str, str]]:
    """The script's spoken lines by number: (who says it, as the shots name them; its words,
    notes in brackets out). A line is spoken when a speaker's label opens it ("MIA:", "Old
    Biscuit (V.O.):"); headings, ★ lines, [tag] lines and directions ("CTA:") are not.
    `talker`: a presenter filmed talking to camera says every line a narrator would read,
    labelled or not (app/omni_talker.py)."""
    from app.clip_takes import OFF_CAMERA

    if talker:
        return {n: (talker, said) for n, said in one_pass_timed.narrated_lines(text)}
    out = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = prompts.unnoted(raw).strip()
        m = check.LABEL.match(line)
        if not m or m[1].upper() in check.NOT_SPEAKERS or line.startswith(prompts.HEADING):
            continue
        if words := line[m.end() :].strip():
            who = m[1].title() if m[1].isupper() else m[1]
            off = f" {m[2]}" if m[2] and OFF_CAMERA.search(m[2]) else ""  # heard, not seen
            out[n] = (who + off, words)
    return out


def long_lines(text: str, most: int, talker: str = "") -> list[int]:
    """The spoken lines too long to say in one clip of `most` seconds (a paragraph of a
    presenter's monologue, a long speech), by the measure a talker's clip is sized to
    (omni_talker: PACE words a second plus ROOM), that have more than one sentence."""
    from app.breakdown_fix import _sentences
    from app.omni_talker import PACE, ROOM

    return [n for n, (_, words) in spoken(text, talker).items()
            if len(words.split()) / PACE + ROOM > most and len(_sentences(words)) > 1]  # fmt: skip


def units(text: str, split: list[int], talker: str = "") -> tuple[str, list[int]]:
    """The script as the plan numbers it, and the script line each numbered row comes from:
    every line as it is, but each of the `split` lines (`long_lines`) as its sentences, one a
    row, each under the line's own speaker label, so the plan can give a long line a sentence
    at a time and no sentence is ever cut. Words are only ever split between sentences
    (breakdown_fix._sentences, as a talker's clips are), never changed."""
    from app.breakdown_fix import _sentences

    said, rows, origin = spoken(text, talker), [], []
    for n, raw in enumerate(text.splitlines(), 1):
        parts = [raw]
        if n in split and n in said:
            words, base = said[n][1], prompts.unnoted(raw).strip()
            head = base[: len(base) - len(words)] if base.endswith(words) else ""
            parts = [head + s for s in _sentences(words)]
        rows += parts
        origin += [n] * len(parts)
    return "\n".join(rows), origin


def to_breakdown(plan: ShootingPlan, text: str, who: dict[str, str], where: dict[str, str],
                 audio: dict | None = None, talker: str = "",
                 origin: list[int] | None = None) -> Breakdown:  # fmt: skip
    """The plan as a breakdown: a scene for each run of clips in one place, a shot for each of
    the plan's, a clip for each of its clips. `who` and `where`: the asset id of each person
    and place the plan names. A script line nobody says (a heading, an action) rides with the
    shot of the next spoken line, so every line is in a shot. `audio` (one_pass_timed.audio):
    the video is timed to a narration or a song, so a shot lasts its time in that track and
    carries the script lines heard under it, however many shots one line runs across.
    `talker`: a presenter filmed on Omni says the lines; a B-roll clip's shots carry the line
    they show (`script_lines`) and say nothing, so the cut lays them over the talker's voice
    (omni_talker.cutaways). `origin`: `text` is the script as the plan numbers it (`units`),
    and this is each of its rows' own script line, which the shots carry."""
    said, scenes, clips, lines = spoken(text, talker), [], [], {}
    origin = origin or list(range(1, len(text.splitlines()) + 1))
    timed = iter(one_pass_timed.spans(plan, audio)) if audio else None
    for c in plan.clips:
        if not scenes or c.place != plan.clips[len(clips) - 1].place:
            n = len(scenes) + 1
            scenes.append(Scene(id=n, heading=c.place or f"Scene {n}", look=c.setting, shots=[]))
        scene, ids, length = scenes[-1], [], 0.0
        screens = [a for a in c.assets if a.startswith("screen:")]
        for k, s in enumerate(c.shots):
            speaker, words = said.get(s.line or 0, (None, None))
            start, end = next(timed) if timed else (0.0, float(s.seconds))
            heard = one_pass_timed.heard(audio, start, end) if timed else [s.line] * bool(words)
            shows = bool(talker) and c.kind == one_pass_timed.BROLL  # laid over the voice
            speaker, words = (None, None) if shows else (speaker, words)
            real = None  # the brand's own clip as this shot (UGC; footage_shot.checked judges it)
            if c.footage and len(c.shots) == 1 and not words:
                real = FootageUse(id=c.footage, start=c.footage_at, sound=False,
                                  end=c.footage_at + end - start)  # fmt: skip
            mine = heard if timed else [origin[n - 1] for n in heard]
            shot = Shot(
                id=f"{scene.id}.{len(scene.shots) + 1}", speaker=speaker, line=words,
                script_lines=mine, action=s.action, reaction=None,
                camera=s.camera, seconds=round(end - start, 2), moment=None,
                character_ids=list(dict.fromkeys(who[p] for p in s.people if p in who)),
                place_id=where.get(c.place), screen_ids=[] if k else screens, footage=real,
            )  # fmt: skip
            scene.shots.append(shot)
            ids.append(shot.id)
            length += end - start
            for n in [] if shows else heard:
                lines.setdefault(n, shot)
        last = c is plan.clips[-1]
        clips.append(Clip(id=c.id, shot_ids=ids, seconds=max(1, math.ceil(length - 0.01)),
                          seam="end" if last else c.shots[-1].action))  # fmt: skip
    shots = [s for scene in scenes for s in scene.shots]
    for n, raw in enumerate(text.splitlines(), 1):
        if raw.strip() and not raw.startswith("SCENE") and n not in lines and shots:
            home = lines[min((k for k in lines if k > n), default=max(lines, default=0))] if (
                lines) else shots[0]  # fmt: skip
            home.script_lines = sorted({*home.script_lines, n if audio else origin[n - 1]})
    return Breakdown(hook=plan.treatment.hook, scenes=scenes, clips=clips)


def _sentence(text: str) -> str:
    text = " ".join((text or "").split())
    return text if not text or text[-1] in '.!?…"”' else f"{text}."


def _in_order(line: str) -> str:
    """The References line with its pictures in the order they're attached."""
    if not line.startswith("References: "):
        return line
    said = re.split(r"\s+(?=\[Image\d+\] is )", line.removeprefix("References: "))
    said.sort(key=lambda x: int(m[1]) if (m := re.match(r"\[Image(\d+)\]", x)) else 0)
    return "References: " + " ".join(said)


def _frame(people: list[str], extras: str) -> str:
    """Who is in the picture, every shot: only they are named in it, so a close-up of one
    person isn't drawn as another the clip also has."""
    told = "; ".join(x for x in (", ".join(people), extras.strip().rstrip(".")) if x)
    return f" Only in frame: {told}." if told else ""


def written(db: Session, project: Project, bd: Breakdown, clip: Clip, told: dict,
            known: dict, lean: int = 0) -> ClipPrompt:  # fmt: skip
    """One clip's prompt and pictures. `told`: its clip in the director's plan (its summary,
    setting, sound and each shot's people, extras and how its line is said); a shot the plan
    no longer matches is written from the breakdown alone. `lean`: 1 leaves out the Setting
    line, 2 the Only in frame notes too (a prompt past its model's limit)."""
    from app import host, talker, voices

    shots = {s.id: s for scene in bd.scenes for s in scene.shots}
    mine = [shots[i] for i in clip.shot_ids if i in shots]
    extra = told.get("shots") or []
    extra = extra if len(extra) == len(mine) else [{} for _ in mine]
    pics = clip_prompts._pictures(known)
    place = next((s.place_id for s in mine if s.place_id), None)
    frame = f"frame:{clip.id}"  # a talker's one opening still (one_pass._opening_still)
    own = [r for r in dict.fromkeys([frame, place, *(told.get("assets") or [])])
           if r and not r.startswith("screen:") and pics.get(r, ("", []))[1]]  # fmt: skip
    seen = ["[Image1] is the first frame." if r == frame else
            (PLACE if r.startswith("place:") else REAL).format(n, clip_prompts._name(pics, r))
            for n, r in enumerate(own, 1)]  # fmt: skip
    sound = (told.get("sound") or "the room's own sound").strip().rstrip(".")
    audio = (SPOKEN if any(s.line for s in mine) else SILENT).format(sound)
    style = _sentence(guides.tokens(looks.drawn(project))["clip_style"].strip())
    if host.on(db, project) and not talker.on(db, project):  # a host is laid over a corner
        style += f" {one_pass_timed.FRAMING}"
    lines = [audio, f"References: {' '.join(seen)}",
             f"Summary: {_sentence(told.get('summary') or ' '.join(s.action for s in mine))}",
             f"Style: {style}"]  # fmt: skip
    if lean < 1 and (told.get("setting") or "").strip():
        lines.append(f"Setting: {_sentence(told['setting'])}")
    sounds = voices.on_omni(db, project)
    for name in dict.fromkeys(OFF.sub("", s.speaker).strip() for s in mine if s.line):
        if words := voices.voice_of(name, sounds):  # the same words in every clip they speak in
            lines.append(f"{name}'s voice: {words.rstrip('.')}.")
    at = 0.0  # a timed video's shots keep their tenths here: `repair_shape` then rounds each
    for k, (s, x) in enumerate(zip(mine, extra, strict=True), 1):  # edge where it falls
        end = round(at + s.seconds, 1)
        frame = "" if lean > 1 else _frame(x.get("people") or [], x.get("extras") or "")
        how = (x.get("how") or "").strip().rstrip(".")
        if s.line and check.VO.search(s.speaker or "") and not model_map.THOUGHT.search(how):
            how = ", ".join(x for x in ("voice-over, lips closed", how) if x)  # the "(V.O.)"
        name = OFF.sub("", s.speaker or "").strip()
        say = (f'{name} (in English{", " + how if how else ""}): "{s.line}"' if s.line
               else "No one speaks.")  # fmt: skip
        lines.append(f"Shot {k} | {at:g}-{end:g} s. {_sentence(s.camera)} {_sentence(s.action)}"
                     f"{frame} {say}")  # fmt: skip
        at = end
    refs = [Reference(kind="image", id=r, role=clip_prompts._name(pics, r)) for r in own]
    draft = ClipPrompt(clip_id=clip.id, seconds=clip.seconds, references=refs,
                       prompt="\n".join([*lines, "Keep: ", audio]))  # fmt: skip
    made = clip_prompts.with_cast(db, project, draft, bd, known)  # the sheets, by the rules
    kept = [_in_order(x) for x in made.prompt.splitlines()
            if x.strip() not in ("References:", "Keep:")]  # fmt: skip
    made = clip_prompts.repair_shape(made.model_copy(update={"prompt": "\n".join(kept)}), bd)
    words = clip_prompts.reword(made.prompt, looks.drawn(project))[0]
    return made.model_copy(update={"prompt": words})


def _fitted(db: Session, project: Project, bd: Breakdown, clip: Clip, told: dict,
            known: dict, row: ProjectClip | None) -> tuple[ClipPrompt, list[str]]:  # fmt: skip
    """The clip's prompt under its model's limit, with room for what a take adds
    (`clip_takes.ROOM`): written leaner while it's over, and said plainly if it still is."""
    from app.clip_takes import ROOM

    model = model_map.of_clip(project, row)
    most = model.prompt_max - ROOM if model.prompt_max else 0
    for lean in (0, 1, 2):
        c = written(db, project, bd, clip, told, known, lean)
        if not most or len(c.prompt) <= most:
            return c, []
    return c, [f"{clip.id}: " + TOO_LONG.format(n=len(c.prompt), most=most, model=model.name)]


def assemble(db: Session, project: Project, row: BreakdownVersion, only=None,
             job_id: int | None = None, by_id: int | None = None,
             remake: bool = False) -> list[str]:  # fmt: skip
    """Write the prompt of each of the breakdown's clips (`only`: those ids) into its row, as
    a clip-prompts run saves them (`clip_prompts.save_clip_prompts`): a clip the plan no
    longer has is removed, a new one added, and a rewritten one keeps its takes as earlier
    takes. `remake`: the plan itself changed these clips, so none keeps a take picked and its
    next take is made. A clip whose words come out the same only moves to this breakdown. The
    ids it wrote anew."""
    from sqlalchemy import delete

    from app import footage_shot

    bd, told = Breakdown.model_validate(row.data), row.data.get(PLAN) or {}
    plan = {c["id"]: c for c in told.get("clips") or []}
    rows = {r.clip_id: r for r in db.scalars(select(ProjectClip).where(
        ProjectClip.project_id == project.id))}  # fmt: skip
    for clip_id in set(rows) - {c.id for c in bd.clips}:  # gone: its takes' files stay
        rows[clip_id].picked_take_id = None
        db.flush()
        db.execute(delete(ClipTake).where(ClipTake.clip_id == rows[clip_id].id))
        db.delete(rows.pop(clip_id))
    known, done = clip_prompts.assets(db, project), []
    real = footage_shot.uses(row.data)  # the brand's own clips: cut from them, never written
    for clip in bd.clips:
        if clip.id in real or (only is not None and clip.id not in only):
            continue
        mine = rows.get(clip.id)
        c, long = _fitted(db, project, bd, clip, plan.get(clip.id) or {}, known, mine)
        problems = clip_prompts.clip_problems(db, project, bd, c) + long
        if mine is None:
            mine = ProjectClip(project_id=project.id, clip_id=clip.id)
            db.add(mine)
        elif mine.prompt == c.prompt and not remake:  # the same words: no new version
            mine.breakdown_id, mine.seconds, mine.problems = row.id, c.seconds, problems
            mine.references = [r.model_dump() for r in c.references]
            continue
        else:
            for take in db.scalars(select(ClipTake).where(ClipTake.clip_id == mine.id)):
                take.prompt = take.prompt if take.prompt is not None else mine.prompt
            clip_prompts.before_change(db, mine)
        mine.breakdown_id, mine.seconds, mine.job_id = row.id, c.seconds, job_id or mine.job_id
        mine.prompt, mine.references = c.prompt, [r.model_dump() for r in c.references]
        mine.problems, mine.kept = problems, []
        mine.approved, mine.prompt_ok, mine.change, mine.auto_fix = False, False, None, None
        if remake:
            mine.picked_take_id = None
        clip_prompts.log_prompt(db, mine, by_id)
        done.append(clip.id)
    return done


def follow(db: Session, project: Project, unmade: bool = False) -> list[str]:
    """After anything changed the shots, the cast or a look: each clip left behind on an older
    breakdown is written again from the newest one, free; one with a take keeps it picked (it
    reads "Out of date" if its words changed: nothing is remade because a look changed, rule
    8). `unmade`: before the takes, each clip with no take yet too, as its looks are now,
    unless a person has edited or read its prompt since. The ids it wrote anew."""
    row = clip_prompts.newest(db, project)
    if row is None or PLAN not in (row.data or {}):
        return []
    rows = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)).all()
    have = {r.clip_id for r in rows}
    todo = {r.clip_id for r in rows if r.breakdown_id != row.id
            or (unmade and not r.picked_take_id and not r.prompt_ok)}  # fmt: skip
    todo |= {c["id"] for c in row.data.get("clips", []) if c["id"] not in have}
    return assemble(db, project, row, todo) if todo else []
