"""The director's song and narration (Freestyle Song and Narrated, the Producer; the Director's
prompt side): in a song or narrated video the audio is the clock, so it comes right after the
treatment and before the plan. `song` makes the version's song takes (the version's style
line; a remake's note is added to that one request, never to the frozen version) and uses one
once they're timed; `narration` makes the narrator's read and uses it. Each is remade once a
run at most. The director judges a timed take without listening: when its first line is
sung (`hook_at`), which lines weren't heard as written (`missing`) and, in a narration, where
the brand's name was heard wrong (`misheard`), so it's read again with a note before the plan."""

import re
from decimal import Decimal

from sqlalchemy.orm import Session

from app import music, narration, song_takes, song_timing, take_words, voices
from app.models.accounts import User
from app.models.brands import Brand
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.songs import SongTake
from app.prompts import check

REMADE = "audio_remakes"  # the run's count of them, a song's or a narration's alike
REMAKES = 2  # a run's song (or narration) made again, with a note (Song-Producer: 2)
HEARD = 0.6  # a line counts as heard as written from this share of its words (take words)
HOOK = 0.5  # the first line sung: half its words heard
CLOSE = 0.8  # a name of more than one word: this close in letters is the name said wrong
NO_SONG = "Refused: this video has no song."
NO_NARRATOR = "Refused: this video has no narrator."
AGAIN = f"Refused: the {{what}} was made again {REMAKES} times this run."
NO_SPEED = ("Refused: `speed` sets an ElevenLabs voice's pace; an English_ voice's pace follows "
            "its `emotion`.")  # fmt: skip
OFF = "Refused: songs aren't switched on here yet."
NO_STYLE = "Refused: the first song needs its style line as the note (genre, vocal, tempo)."
REFUSED = (music.REFUSED, music.REFUSED_IN_VIDEO)  # the words or style refused: never as is


def kind(db: Session, project: Project) -> str | None:
    """ "song" or "narrated" for a video timed to its audio; else None."""
    found = narration.video_kind(db, project)
    return found if found in narration.TIMED else None


def _bare(word: str) -> str:
    """A word as compared: "Fomo’s" reads "fomo" (the possessive dropped)."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"'s$", "", word.lower().replace("’", "'").strip(
        ".,!?;:…\"“”")))  # fmt: skip


def _near(heard: list[str], name: list[str]) -> bool:
    """A run of heard words that is the brand's name said wrong: each word one letter off at
    most, or, for a name of more than one word, its letters close ("Iron Pause")."""
    if heard == name:
        return False
    if all(h == n or take_words._off_by_one(h, n) for h, n in zip(heard, name, strict=True)):
        return True
    joined, want = "".join(heard), "".join(name)
    return len(name) > 1 and joined[:1] == want[:1] and take_words._close(joined, want) >= CLOSE


def misheard(timing: dict | None, brand: str, script: str = "") -> list[dict] | None:
    """The brand's name heard wrong in a timed narration ("Fobo" for fomo, "Iron Pause" for
    Iron Paws), from its words on the trimmed track; None until it's timed. Words the script
    itself has, as written ("user"), are never flagged."""
    if timing is None:
        return None
    words = timing.get("words") or []
    name = [b for w in brand.split() if (b := _bare(w))]
    written = f" {' '.join(_bare(w) for w in script.split())} "
    found, i = [], 0
    while name and i + len(name) <= len(words):
        run = words[i : i + len(name)]
        bare = [_bare(w["word"]) for w in run]
        if _near(bare, name) and f" {' '.join(bare)} " not in written:
            found.append({"word": brand, "heard": " ".join(w["word"] for w in run),
                          "at": run[0]["start"]})  # fmt: skip
            i += len(name)
        else:
            i += 1
    return found


def _missing(take: SongTake, lines: list[dict], brand: str = "") -> list[str]:
    """Lines not heard as written. A song's: under HEARD of its words. A narration's: any word
    lost, by its letters against everything heard, as `letters` compares (one dropped
    "probiotics" is a miss), its speaker label left out ("NARRATOR:", video 271). On a read
    with the script's words in order but for a few written another way (COVERED: "10" for
    "ten"), only a line with half its words or more lost, or with the `brand`'s name when
    nothing heard says it."""
    if take.kind != narration.KIND:
        return [x["text"] for x in lines if (x.get("heard") or 0) < HEARD]
    words = (take.timing or {}).get("words") or []
    script = " ".join(check.narration_text(x["text"]) for x in lines)
    heard = narration.letters(words)
    if narration.covered(script, words) >= narration.COVERED:
        name = narration.plain(brand)
        unsaid = bool(name) and name not in heard  # a dropped brand is a small share
        return [x["text"] for x in lines if (x.get("heard") or 0) <= 0.5
                or unsaid and name in narration.plain(x["text"])]  # fmt: skip
    said = [(x["text"], check.narration_text(x["text"])) for x in lines]  # never a label
    return [text for text, words in said if narration.letters([{"word": words}]) not in heard]


def _take(db: Session, take: SongTake, used: int | None, brand: str = "") -> dict:
    status = song_takes.state(db, take)[0]
    timing = take.timing or {}
    lines = timing.get("lines") or []
    sung = [x for x in lines if (x.get("heard") or 0) >= HOOK]
    gaps = [b["start"] - a["end"] for a, b in zip(sung, sung[1:], strict=False)]
    timing_job = db.get(Job, take.timing_job_id) if take.timing_job_id else None
    again = status == "timing" and timing_job is not None and bool(
        timing_job.retry_of_id or timing_job.input.get(song_takes.REREAD))  # fmt: skip
    return {"id": take.id, "number": take.number, "state": status, "used": take.id == used,
            **({"note": "Its timing failed; reading it again (free)."} if again else {}),
            "preferred": bool(take.preferred), "timed": take.timing is not None,
            "seconds": timing.get("seconds"),
            "sections": [s.get("name") for s in timing.get("sections") or []],
            "hook_at": sung[0]["start"] if sung else None,
            "longest_gap": round(max(gaps), 2) if gaps else None,  # an instrumental break
            "tail": round(timing["seconds"] - sung[-1]["end"], 2) if sung else None,  # outro
            "missing": _missing(take, lines, brand) if take.timing is not None else None,
            "pace": timing.get("pace"),  # words a second while speaking, as measured
            **({"misheard": misheard(take.timing, brand, take.lyrics)}
               if take.kind == narration.KIND else {}),
            "extras": _extras(take)}  # fmt: skip


def _extras(take: SongTake) -> list[dict] | None:
    """Sung or said but not in the words (ad-libs, an extra chorus, a note read aloud); None
    until timed. Timings read before extras were saved work them out from their words."""
    if take.timing is None:
        return None
    if "extras" in take.timing:
        return take.timing["extras"]
    words = take.timing.get("words") or []
    if take.kind == narration.KIND:
        return narration.extras(check.narration_text(take.lyrics), words)
    return song_timing.extras(take.lyrics, words)


def state(db: Session, project: Project) -> dict | None:
    """What the director reads: {state none | making | ready | failed, takes, used_take_id};
    a song's also has the `style` it's sung in and the brand's `recent_styles`, a
    narration's the `say` note it's read again with when the brand's name is heard wrong."""
    found = kind(db, project)
    if found is None:
        return None
    brand = db.get(Brand, project.brand_id)
    made = song_takes.for_video(db, project)
    takes = [_take(db, t, project.song_take_id, brand.name) for t in made]
    states = {t["state"] for t in takes}
    now = ("none" if not takes else "making" if states & {"making", "timing"}
           else "ready" if "ready" in states else "failed")  # fmt: skip
    out = {"state": now, "takes": takes, "used_take_id": project.song_take_id}
    if found == "narrated":  # the note a narration with the name wrong is read with
        out["say"] = narration.SAY  # a short tag: a sentence in one is read aloud
        used = next((t.voice for t in made if t.id == project.song_take_id), None)
        said = used or narrator(db, project)
        if own := voices.for_director(db, project.workspace_id, project.brand_id, said):
            out["voice"] = own  # a cloned voice's state and when it may expire
        if note := voices.host_note(db, project):
            out["voice_note"] = note  # the host's own voice was removed: say what to do
        out["pace_wanted"] = target(db, project)  # the style's words a second
        from app import audition

        if heard := audition.status(db, project):  # the presenter's voice is chosen first
            out["audition"] = heard
    if found == "song":
        used = [t for t in made if t.id == project.song_take_id]
        take = (used or sorted(made, key=lambda t: t.id))[-1] if made else None
        draft = db.get(ScriptDraft, project.script_draft_id)
        out["style"] = (music.sung_style(db.get(Job, take.job_id).input) if take
                        else draft.style_line.strip())  # fmt: skip
        out["recent_styles"] = music.recent_styles(db, project.brand_id)
    return out


def _on(db: Session, draft: ScriptDraft) -> bool:
    """As the songs route's own switch (routes/songs.songs_on), from the server's settings."""
    settings = _settings()
    if song_takes.narrated(db, draft):
        return bool(settings.fake_providers or settings.generation_enabled)
    return bool(settings.fake_providers or settings.kie_suno)


def run(db: Session, user: User, project: Project, decision: dict, run: dict) -> str:
    """The tool: with `take_id`, use that timed take (free); with no note and a timed take,
    the best one; else make takes. The first song of a version with no style line takes its
    style from the note (the director's music words); after that a note is a remake, REMAKES
    a run (counted in `run`). A MiniMax narrator's `emotion` and `reading` ask like a note,
    and so does an ElevenLabs narrator's `speed` (its pace) on a remake."""
    from app import one_pass

    tool, note = decision["tool"], (decision.get("note") or "").strip()
    delivery = {k: decision[k] for k in ("emotion", "reading") if decision.get(k)}
    if delivery and (speed := _speed(db, project, delivery.get("emotion"))):
        delivery["speed"] = speed  # set from the last read's measured pace
    found = kind(db, project)
    if found is None or (tool == "song") != (found == "song"):
        return NO_SONG if tool == "song" else NO_NARRATOR
    pace = decision.get("speed") if found == "narrated" and not delivery else None
    pace = pace if pace and pace != 1 else None  # an ElevenLabs remake's pace (below)
    asked = note or delivery or pace
    draft = db.get(ScriptDraft, project.script_draft_id)
    what = "song" if found == "song" else "narration"
    takes = song_takes.for_video(db, project)
    ready = [t for t in takes if song_takes.state(db, t)[0] == "ready"]
    before = one_pass.on(project) and not run.get("ok", True)  # its plan is timed to it
    left = run.get(REMADE, 0) < REMAKES  # a remake is left to fix a take that says more
    if (chosen := decision.get("take_id")) is not None:
        take = next((t for t in ready if t.id == chosen), None)
        if take is None:
            return f"Refused: take {chosen} isn't a finished {what} of this video."
        if left and (extra := narration.says_more(take)):
            return "Refused: " + narration.SAYS_MORE.format(extra)
        song_takes.use_in_video(db, project, take)
        _follow(db, project, user)
        return f"Using take {take.number} for the {what}."
    if ready and not asked:
        if project.song_take_id in {t.id for t in ready}:
            return f"The {what} is set: take {_number(db, project.song_take_id)}."
        fit = [t for t in ready if not narration.says_more(t)]  # never a note read aloud,
        if not fit and left:  # while a remake can fix it; then the best of them
            return "Refused: " + narration.SAYS_MORE.format(narration.says_more(ready[-1]))
        fit = fit or ready
        best = next((t for t in fit if t.preferred), None) or min(
            fit, key=lambda t: _rank(_take(db, t, None), t.id))  # fmt: skip
        song_takes.use_in_video(db, project, best)
        _follow(db, project, user)
        return f"Using take {best.number} for the {what}."
    if takes and not asked:
        if any(song_takes.state(db, t)[0] in ("making", "timing") for t in takes):
            return f"Refused: the {what} is still being made."  # a job of it is running
        # Nothing runs and nothing is ready: a take whose timing failed is read again first
        # (free, once after its own retry; Carry on after a stop gets here too), then it's
        # failed, as one the service didn't make: a remake, or another take.
        if again := next((t for t in takes if song_takes.state(db, t)[0] == "timing_failed"
                          and song_takes.reread_once(db, t)), None):  # fmt: skip
            song_takes.reread(db, again, user)
            return f"Reading take {again.number}'s timing again: free."
        if fetched := next((t for t in takes if song_takes.fetch_again(db, t, once=True)), None):
            song_takes.try_again(db, user, fetched)  # made and paid for, only not saved
            return f"Fetching the {what} again: it was made, only saving it failed. Free."
        failed = takes
        reason = song_takes.state(db, failed[0])[1] or ""
        from app.worker import LATE

        if reason == LATE.format("The music service"):  # may still finish there, and be charged
            return f"Refused: {reason}"  # never a second paid request on its own
        if reason in REFUSED or run.get("song_retries", 0) >= 1:  # the same would fail again
            return f"Refused: the {what} didn't come out ({reason}) Make it again with a note."
        last = run.get("song_note", "")  # the same request again: its style line too
        voice = run.get("song_voice") or narration.VOICE  # a narration keeps its voice
        song_takes.make(db, user, draft, project, kie=_real(db, found), note=last, voice=voice,
                        delivery=run.get("song_delivery"), before=before)  # fmt: skip
        run["song_retries"] = run.get("song_retries", 0) + 1  # charged only if it's made
        if any(song_takes.state(db, t)[0] == "timing_failed" for t in takes):
            return (f"Making the {what} again: its timing couldn't be read, so nothing used "
                    "it. It's charged only once it's made.")  # fmt: skip
        return f"Trying the {what} again: the service failed, nothing was charged."
    if takes and run.get(REMADE, 0) >= REMAKES:
        return AGAIN.format(what=what)
    if found == "song" and not note and not draft.style_line.strip():
        return NO_STYLE  # free: never a song with no genre, vocal or tempo (QA-10)
    if not _on(db, draft):
        return OFF
    kept = next((t.voice for t in takes if t.id == project.song_take_id), None)  # a remake's
    if kept and not voices.usable(db, project.workspace_id, project.brand_id, kept):
        kept = None  # its voice was removed since: the video's own voice now
    named = decision.get("voice")  # the director's: a person's pick or the video's own wins
    voice = narrator(db, project, named, kept) if found == "narrated" else _voice(db, project)
    if not voices.usable(db, project.workspace_id, project.brand_id, voice):
        return f"Refused: the narrator's voice is one of {', '.join(narration.VOICES)}."
    if pace and voice not in narration.ELEVENLABS and not note:
        return NO_SPEED  # nothing would change: a MiniMax read's pace follows its emotion
    if pace and takes and voice in narration.ELEVENLABS:  # the first read: the voice's own
        delivery = {"speed": pace}
    song_takes.make(
        db,
        user,
        draft,
        project,
        kie=_real(db, found),
        note=note,
        voice=voice,
        delivery=delivery,
        before=before,
    )  # a reading that changes a word: a 422
    run["song_note"], run["song_voice"], run["song_delivery"] = note, voice, delivery
    if takes:  # a remake; the first song's note is its style line, not a remake
        run[REMADE] = run.get(REMADE, 0) + 1
    said = ", ".join(
        [
            *([note] if note else []),
            *([f"speed {pace}"] if pace and delivery.get("speed") == pace else []),
        ]
    )
    return f"Making the {what}{f' ({said})' if said else ''}."


def _follow(db: Session, project: Project, user: User) -> None:
    """A plan made already moves to the take now in use, free, as a person's switch does
    (routes/songs: the owner's changed line read again, line_change)."""
    from app import song_breakdown

    if song_breakdown.follow_take(db, project, user.id) is not None:
        db.commit()


def target(db: Session, project: Project) -> tuple[float, float] | None:
    """The words a second the video's style (else its format) keeps, from its guide."""
    from app import guides
    from app.script_library import format_id

    script = narration.video_script(db, project)
    return guides.pace(project.look or "house", format_id(script)) if script else None


def _speed(db: Session, project: Project, emotion: str | None) -> float | None:
    """A MiniMax remake's speed: the last read in the same emotion, measured, brought to the
    style's pace (narration.retimed: "measure, don't guess"); None leaves the emotion's own."""
    want = target(db, project)
    done = [t for t in song_takes.for_video(db, project)
            if t.timing and t.timing.get("pace") and t.job_id]  # fmt: skip
    for take in sorted(done, key=lambda t: (t.id != project.song_take_id, -t.id)):
        made = narration.delivery(db.get(Job, take.job_id).input)
        if made and want and made["speed"] and (made["emotion"] or "auto") == (emotion or "auto"):
            return narration.retimed(made["speed"], take.timing["pace"], want) or made["speed"]
    return None


def narrator(
    db: Session, project: Project, named: str | None = None, kept: str | None = None
) -> str:
    """The voice a narration is read in, and before one is made the one it will be, in one order
    for the Cast tab (routes/host) and the narration (QA #1395): a person's pick for the video
    (its settings or a voice card's answer, S4-01), else the video's own (its presenter's, else
    its style's, e.g. Dr. Pickle's clone), else the director's `named` one, else the one in use
    (`kept`), else the default (_voice)."""
    return (voices.picked(db, project) or voices.default_for(db, project) or named or kept
            or _voice(db, project))  # fmt: skip


def _voice(db: Session, project: Project) -> str:
    """The narrator when none is picked: a person's for this video, else the video's own (its
    host's or its style's, e.g. Dr. Pickle's clone), else "" for a presenter nobody has chosen
    a voice for yet (their audition picks it, app/audition.py), else narration's."""
    from app import audition

    if own := voices.picked(db, project) or voices.default_for(db, project):
        return own
    return "" if audition.needed(db, project) else narration.VOICE


def _real(db: Session, found: str) -> float:
    """A real song through KIE's price (song_takes.real_songs); a narration is never one."""
    return 0.0 if found == "narrated" else song_takes.real_songs(db, _settings())


def _rank(take: dict, take_id: int) -> tuple:
    """The best take first: fewest lines missing, then the shorter (cheaper to film)."""
    return (len(take["missing"] or []), take["seconds"] or 0, take_id)


def still_wrong(state: dict) -> str:
    """For the delivery note: the brand's name the narration in use still says wrong, or the
    words it says that the script doesn't have, once its remakes are used (director.md: say
    what's off)."""
    audio = state.get("narration") or {}
    used = next((t for t in audio.get("takes") or [] if t["used"]), None)
    said = []
    if used and used.get("misheard"):
        w = used["misheard"][0]
        said.append(f"The narration still says “{w['heard']}” for {w['word']} at {w['at']:.1f} s")
    if used and used.get("extras"):
        x = used["extras"][0]
        said.append(f"The narration says “{x['text']}” at {x['start']:.1f} s, which the "
                    "script doesn't have")  # fmt: skip
    return (f"{'. '.join(said)}: it was read again as often as allowed, so listen before you "
            "share it.") if said else ""  # fmt: skip


def audio_move(state: dict, go, style: str, voices) -> dict | None:
    """A run's next move on its song or narration, with no model deciding (the stand-in
    director's, and every one-pass run's): make it, wait for it, then use its best take; a
    failed one is tried again (free when the service failed; refused, it says so). A narration
    that says the brand's name wrong is read again with the pronunciation note (while
    narrations are left), and the plan follows one that says it right. `style`: the style line
    a song with none is first made in; `voices`: who reads for a presenter with no voice yet
    (app/audition.py). None: the audio is in use, so the plan is next."""
    tool = "song" if "song" in state else "narration" if "narration" in state else None
    audio = state.get(tool) if tool else None
    if audio is None:
        return None
    if tool == "narration" and (said := _say_it_right(audio, state, go)):
        return said
    if audio.get("used_take_id"):
        return None
    what = "song" if tool == "song" else "narration"
    if heard := audio.get("audition"):  # the presenter's voice first: the person picks it
        if heard["state"] == "asked":
            return go("wait", f"{heard['who']}'s voice is being auditioned.")
        who = heard["who"]
        return go(
            "ask",
            f"{who}'s voice first: everything is timed to it.",
            ask={
                "kind": "voice",
                "subject": who,
                "topic": f"{who}'s voice"[:80],
                "question": f"Which voice is {who}?",
                "voices": list(voices),
                "why": "Each reads the script's opening. The one you pick is saved on them.",
            },
        )
    if audio["state"] == "none":
        style = {} if audio.get("style", True) else {"note": style}  # a song's first
        return go(tool, f"The {what} first: its timing is what the shots follow.", **style)
    if audio["state"] == "making":
        return go("wait", f"The {what} is being made.")
    if audio["state"] == "ready":
        return go(tool, f"The {what} is made and timed: use its best take.")
    return go(tool, f"The {what} didn't come out: try it again.")  # free once; then a note


def _say_it_right(audio: dict, state: dict, go) -> dict | None:
    """A narration that says the brand's name wrong, before the plan: read again with the
    pronunciation note while narrations are left, then the one that says it right is used."""
    if audio["state"] not in ("ready", "making") or state["shots"] != "none":
        return None
    timed = [t for t in audio["takes"] if t["state"] == "ready" and t["timed"]]
    used = next((t for t in timed if t["used"]), None)
    good = [t for t in timed if not t.get("misheard")]
    if used and not used.get("misheard") or not timed:
        return None
    if audio["state"] == "making":
        return go("wait", "The narration is being read again.")
    if good:
        return go("narration", "This narration says the brand's name right: use it.",
                  take_id=good[-1]["id"])  # fmt: skip
    wrong = timed[-1]["misheard"][0]
    if state.get("allowed", {}).get("narrations_left", 0) > 0:
        return go("narration", f"The narration says “{wrong['heard']}” for {wrong['word']} at "
                  f"{wrong['at']:.1f} s: read it again.", note=audio["say"])  # fmt: skip
    return None


def _settings():
    from app.settings import get_settings

    return get_settings()


def _number(db: Session, take_id: int) -> int:
    return db.get(SongTake, take_id).number


def price(db: Session, draft: ScriptDraft) -> Decimal:
    """What a run's song or narration can cost at most: its first request and one remake."""
    from app.credits import estimate
    from app.models.script_library import Script

    script = db.get(Script, draft.script_id)
    if script.kind not in narration.TIMED or song_takes.preferred(db, draft):
        return Decimal(0)  # a version with a song already: its card has it (version_cost)
    ws = script.workspace_id
    if script.kind == "narrated":
        job = narration.job(draft.text)
        one = estimate(db, ws, "speech", song_takes._units(job), job)
    else:
        one = estimate(db, ws, "music", Decimal(1), {})
    return one * (1 + REMAKES)
