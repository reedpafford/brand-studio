"""The director asks (v6 piece B; boards S4-01 to S4-04, S3-02, S3-05 to S3-07, S9-01).

One `Ask` row per card. A question comes from the director's `ask` move: the brand's saved
items first, then Upload, Reply or Generate options (a price first; what it makes stays with
this video, rule 12). The director waits only on that point and keeps working. A saved pick is
reused next time without asking. A story choice carries the director's pick and a time; past
it, the director goes with its pick and says so (rule 37). A money card is made when a job on
a video is held for an OK (`held`, from `enqueue`): the start of a run (Make it), a step past
the video's budget, or the director past its own limit (rule 34). Its state is read from its
held jobs, so the job routes' Approve, Decline and Withdraw keep it right too."""

from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import ask_options as opts
from app.db import utcnow
from app.models.accounts import User
from app.models.asks import Ask
from app.models.brands import Brand, BrandScreen
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem
from app.models.projects import Project

QUESTIONS = ("cast", "presenter", "voice", "place", "product", "brand_item", "story", "question")
MONEY = ("start", "budget", "own", "plan")  # Make it; past the budget; its own limit; planning
UPLOADS = ("cast", "presenter", "voice", "place", "product", "brand_item")
STORY_WAIT = timedelta(minutes=30)  # a story choice's time on the card (rule 37)
START = "start_run"  # in a run's held first paid turn: the start-of-run OK (S3-02)
BEFORE = "before_ok"  # in a job: planning before Make it, on the video's planning allowance
PLAN_OK = "plan_ok"  # in a held plan change: past the allowance, the owner's OK first
PLANNING = "Waiting for the owner's OK: planning before Make it has used its allowance."
OPEN = ("open", "uploading")
NOT_NEEDED = "This question is no longer needed."
LOCKED = "{} is locked in this video: unlock it in Cast to change who plays them."
NOT_WAITING = "This isn't waiting for an OK any more."
KEPT = "Kept as it is. Nothing was charged for it."


def _now():
    return utcnow()


# --- The director's move --------------------------------------------------------------------


def asked(db: Session, project: Project, run_id: str | None, move: dict) -> str:
    """The director's `ask` move, in plain words for its log: a new card, a saved answer used
    without asking, or (with `ask_id`) a card it no longer needs."""
    if close := move.get("ask_id"):
        ask = db.get(Ask, close)
        if ask is None or ask.project_id != project.id or ask.kind in MONEY:
            return f"Refused: there's no question {close} on this video."
        if ask.state not in OPEN:
            return f"Refused: question {close} is already answered."
        ask.state, ask.closed = "not_needed", (move.get("closed") or "").strip()[:500]
        opts.stop_options(db, ask)
        db.commit()
        return f"No longer needed: {ask.question}"
    kind, question = move.get("kind"), (move.get("question") or "").strip()
    if kind not in QUESTIONS or not question:
        return "Refused: an ask needs its kind and its question."
    subject = (move.get("subject") or "").strip()[:120]
    role = _slot(db, project, subject) if kind in ("cast", "presenter") else None
    if role is not None and locked(project, role):
        return f"Refused: {role.role} is locked in this video; use that look."
    if used := reused(db, project, kind, subject):
        ask = Ask(workspace_id=project.workspace_id, project_id=project.id, run=run_id,
                  kind=kind, topic=(move.get("topic") or "")[:80], subject=subject,
                  question=question, state="answered", answered_at=_now(),
                  answer={"how": "saved", "option": used["id"], "name": used["name"],
                          "file_id": used["file_id"], "reused": True})  # fmt: skip
        db.add(ask)
        _effect(db, None, project, ask)
        db.commit()
        brand = db.get(Brand, project.brand_id)
        return f"{used['name']} is saved in {brand.name}, so I used that."
    done = next((a for a in db.scalars(select(Ask).where(
        Ask.project_id == project.id, Ask.kind == kind, Ask.state == "answered"))
        if a.question == question or subject and _same(a.subject, subject)), None)  # fmt: skip
    if done is not None:  # decided already: never asked again (Reed, 4 Nov)
        said = (done.answer or {}).get("name") or (done.answer or {}).get("text") or "answered"
        return f"Refused: that's decided already (question {done.id}: {said})."
    same = db.scalar(select(Ask.id).where(
        Ask.project_id == project.id, Ask.kind == kind, Ask.question == question,
        Ask.state.in_(OPEN)))  # fmt: skip
    if same:
        return f"Refused: that question is already waiting (question {same})."
    choices = [{"key": chr(65 + n), "title": str(c.get("title", ""))[:200],
                "why": str(c.get("why", ""))[:300]}
               for n, c in enumerate(move.get("choices") or []) if c.get("title")][:4]  # fmt: skip
    if kind == "story" and len(choices) < 2:
        return "Refused: a story choice needs at least two choices and your pick."
    pick = _pick(db, project, kind, move.get("pick"), choices)
    db.add(Ask(workspace_id=project.workspace_id, project_id=project.id, run=run_id, kind=kind,
               topic=(move.get("topic") or "")[:80], subject=subject, question=question[:500],
               why=(move.get("why") or "")[:500], describe=(move.get("describe") or "")[:500],
               choices=choices, pick=pick,
               decide_at=_now() + STORY_WAIT if kind == "story" else None))  # fmt: skip
    db.commit()
    return f"Asked: {question}"


def _pick(db: Session, project: Project, kind: str, said, choices: list[dict]) -> str | None:
    """The director's pick as an option id ("item:12") or a choice's key ("A")."""
    said = str(said or "").strip()
    if kind == "story":
        keys = [c["key"] for c in choices]
        return said.upper()[:1] if said.upper()[:1] in keys else keys[0]
    found = next((o for o in opts.saved(db, project, kind) if said and _same(o["name"], said)),
                 None)  # fmt: skip
    return found["id"] if found else None


def _same(a: str, b: str) -> bool:
    from app.cast_roles import same

    return same(a, b)


def reused(db: Session, project: Project, kind: str, subject: str) -> dict | None:
    """A saved item that answers this already, so nobody is asked again: one named as the
    subject, or the saved pick an earlier card in this brand got for the same subject."""
    if kind not in opts.WORDS and kind not in ("product", "voice") or not subject:
        return None
    options = {o["id"]: o for o in opts.saved(db, project, kind)
               if kind != "voice" or o["id"].startswith("voice:")}  # an app voice: ask  # fmt: skip
    if named := next((o for o in options.values() if _same(o["name"], subject)), None):
        return named
    earlier = db.scalars(select(Ask).join(Project, Project.id == Ask.project_id).where(
        Project.brand_id == project.brand_id, Ask.kind == kind, Ask.state == "answered")
        .order_by(Ask.id.desc())).all()  # fmt: skip
    for ask in earlier:
        if _same(ask.subject, subject) and (ask.answer or {}).get("how") == "saved":
            if (found := options.get(ask.answer.get("option"))) is not None:
                return found
    return None


# --- Answers ----------------------------------------------------------------------------------


def answer(db: Session, user: User, ask: Ask, body: dict, storage=None) -> None:
    """A person's answer, in the chat or in Needs you (the same answer): a saved pick, an
    upload (kept with this video), a reply, a generated option, a story choice, or a money
    card's Make it, Approve, Keep it as it is, Decline or Withdraw. An answered card can be
    changed: the newest answer wins and the director reads it on its next turn."""
    from app import director

    project = db.get(Project, ask.project_id)
    how = body.get("how")
    if ask.kind in MONEY:
        return _money(db, user, ask, project, how)
    if ask.state == "not_needed":
        raise HTTPException(409, NOT_NEEDED)
    role = _slot(db, project, ask.subject) if ask.kind in ("cast", "presenter") else None
    if role is not None and locked(project, role):
        raise HTTPException(409, LOCKED.format(role.role))
    if how == "saved":
        found = next((o for o in opts.saved(db, project, ask.kind)
                      if o["id"] == body.get("option")), None)  # fmt: skip
        if found is None:
            raise HTTPException(422, "Pick one of the saved items on the card.")
        data = {"how": how, "option": found["id"], "name": found["name"],
                "file_id": found["file_id"]}  # fmt: skip
    elif how == "upload":
        data = {"how": how, **_upload(db, user, ask, body.get("file_id"))}
    elif how == "reply":
        text = (body.get("text") or "").strip()
        if not text:
            raise HTTPException(422, "Write your answer first.")
        data = {"how": how, "text": text[:2000]}
    elif how == "option":
        made = opts.options(db, ask)
        n = body.get("option")
        if not isinstance(n, int) or not 0 <= n < len(made) or not made[n]["file_id"]:
            raise HTTPException(422, "Pick one of the options that's made.")
        data = {"how": how, "option": n, "name": f"Option {n + 1}", "file_id": made[n]["file_id"]}
    elif how == "clone" and ask.kind == "voice":  # "Upload a sample · Clone it once" (#1314)
        from app import voices
        from app.routes.files import get_file

        stored = get_file(db, user, int(body.get("file_id") or 0), "audio")
        same = (ask.answer or {}).get("how") == how and ask.answer.get("file_id") == stored.id
        if same and state(db, ask) != "failed":  # a failed one charged nothing: try it again
            raise HTTPException(409, "That sample is cloned already.")  # one charge a sample
        named = (body.get("text") or ask.subject or ask.topic or "Voice").strip()
        made = voices.clone(db, user, project.brand_id, storage, stored, named, "")
        data = {
            "how": how,
            "option": f"voice:{made.id}",
            "name": made.name,
            "file_id": stored.id,
            "before": project.voice,  # the video's voice before: back if the clone is withdrawn
            **({"reused": True} if made.provider_voice_id else {}),
        }  # the brand's, no charge
    elif how == "choice" and ask.kind == "story":
        found = next((c for c in ask.choices if c["key"] == body.get("choice")), None)
        if found is None:
            raise HTTPException(422, "Pick one of the choices on the card.")
        data = {"how": how, "choice": found["key"], "name": found["title"]}
    else:
        raise HTTPException(422, "That isn't a way to answer this card.")
    opts.stop_options(db, ask)
    ask.answer, ask.state, ask.answered_by_id, ask.answered_at = data, "answered", user.id, _now()
    _effect(db, user, project, ask)
    db.commit()
    director.wake(db, project)


def _voice(db: Session, user: User | None, project: Project, ref: str) -> None:
    """A voice card's answer is the person's voice for this video (`projects.voice`), set
    through the settings' own check and logged as theirs, so the director keeps it."""
    from app import settings_move, voices

    try:
        ref = voices.checked(db, project, ref)
    except HTTPException:
        return  # removed or another brand's since: the card stays answered, the voice unset
    was, project.voice = project.voice, ref
    if was != ref:
        settings_move.log(project, user or db.get(User, project.created_by_id), "voice", was,
                          ref, "person")  # fmt: skip


def _upload(db: Session, user: User, ask: Ask, file_id) -> dict:
    """An upload is used for this video only (rule 12): kept on the card, never the brand's."""
    from app.routes.files import get_file

    if ask.kind not in UPLOADS:
        raise HTTPException(422, "This question takes a reply in words.")
    stored = get_file(db, user, int(file_id or 0))
    kinds = ("audio", "video") if ask.kind == "voice" else ("image", "video")
    if stored.content_type.split("/")[0] not in kinds:
        raise HTTPException(422, "Upload a voice sample." if ask.kind == "voice"
                            else "Upload a photo, a still or a clip.")  # fmt: skip
    return {"file_id": stored.id, "name": stored.filename}


def uploading(db: Session, ask: Ask, on: bool) -> None:
    """The card shows an upload going up (S4-03), and goes back to open if it's cancelled."""
    if ask.kind not in UPLOADS or ask.state not in OPEN:
        raise HTTPException(409, NOT_NEEDED if ask.state == "not_needed" else "It's answered.")
    ask.state = "uploading" if on else "open"
    db.commit()


def _effect(db: Session, user: User | None, project: Project, ask: Ask) -> None:
    """What an answer changes by itself, free: a cast role or the presenter gets the saved
    character, or a look made for this video from the picture (its sheet is drawn by the
    director's make_looks; never saved to the brand); a product shot's saved still picks that
    product's variant for this video; a narrator voice is the one the narration is read in
    (`voice`). Every other answer steers the director, who reads it on its next turn."""
    from app import cast_roles
    from app.routes import project_assets

    data = ask.answer or {}
    option = str(data.get("option", ""))
    if ask.kind == "voice" and option.startswith(("stock:", "voice:")):  # the video's narrator
        _voice(db, user, project, option)
        return
    if ask.kind == "product" and data.get("how") == "saved" and option.startswith("screen:"):
        shot = db.get(BrandScreen, int(option.split(":")[1]))
        if shot is not None and shot.product and shot.variant:
            project.product_variants = {**(project.product_variants or {}),
                                        shot.product: shot.variant}  # fmt: skip
        return
    if ask.kind == "place":  # the place the plan's shots are at, by its name (S-gaps-07 A)
        from app.routes import cast

        return cast.answer_place(db, user or db.get(User, project.created_by_id), project,
                                 ask.subject, data)  # fmt: skip
    if ask.kind not in ("cast", "presenter"):
        return
    slot = _slot(db, project, ask.subject)
    if slot is None or locked(project, slot):  # no such role, or its look is fixed
        return
    who = user or db.get(User, project.created_by_id)
    if data.get("how") == "saved" and str(data.get("option", "")).startswith("item:"):
        item = db.get(LibraryItem, int(data["option"].split(":")[1]))
    elif data.get("how") in ("upload", "option") and _picture(db, data.get("file_id")):
        item = LibraryItem(workspace_id=project.workspace_id, kind=Kind.character,
                           name=cast_roles.short(slot.role) or slot.role,
                           notes=slot.description or slot.role, owner_project_id=project.id,
                           sheet_look=project.look or "house")  # fmt: skip
        if data["how"] == "option":  # drawn as a sheet in the video's look: it is the look,
            item.sheet_file_id, item.sheet_approved = data["file_id"], True  # this video's own
        else:  # a photo is only source material: make_looks draws its sheet
            item.source_photo_file_id = data["file_id"]
        db.add(item)
        db.flush()
        project.slot_looks = {**project.slot_looks, str(slot.id): item.id}
    else:
        return
    project_assets._cast(db, who, project, slot, item)


def _slot(db: Session, project: Project, subject: str):
    """The video's role a cast or presenter card is about, by the script's name for it."""
    from app import cast_roles

    return next((s for s in cast_roles.video_slots(db, project)
                 if subject and cast_roles.same(s.role, subject)), None)  # fmt: skip


def locked(project: Project, slot) -> bool:
    """That role's look is fixed: on the script, the video's whole cast locked, or the role
    alone (the Cast tab's Lock, `locks["roles"]` as "slot:N", #1324's locks.role_locked)."""
    from app import locks

    roles = (project.locks or {}).get("roles") or []
    return bool(slot.library_item_id) or locks.locked(project, "cast") or f"slot:{slot.id}" in roles


def _picture(db: Session, file_id) -> bool:
    from app.models.files import StoredFile

    stored = db.get(StoredFile, file_id or 0)
    return bool(stored and stored.content_type.startswith("image/"))


# --- State ------------------------------------------------------------------------------------


def state(db: Session, ask: Ask) -> str:
    """open, uploading, generating, ready, failed, held, answered or not_needed (the
    viewer-dependent "answered by the owner" is `by_owner`)."""
    if ask.kind in MONEY:
        return _money_state(db, ask)[0]
    if ask.state == "answered" and (ask.answer or {}).get("how") == "clone":
        return _cloned(db, ask)
    if ask.state != "open" or not ask.rounds:
        return ask.state
    made = opts.options(db, ask)
    states = {o["state"] for o in made}
    if str(JobStatus.needs_owner_approval) in states:
        return "held"
    if states & {str(JobStatus.queued), str(JobStatus.running)}:
        return "generating"
    return "ready" if any(o["file_id"] for o in made) else "failed"


NOT_YOURS = "Only whoever asked for this clone, or the owner, can withdraw it."
STARTED = "This clone has started or ended already, so it can't be withdrawn now."


def withdraw_clone(db: Session, user: User, ask: Ask) -> bool:
    """Withdraw a voice card's clone that hasn't started (an editor's, waiting for the owner's
    OK): its job is cancelled (nothing charged), a voice row it made is removed (`voices.
    withdrawn`), the video's voice is put back, and the card is open again (rule 22: the
    editor always has a way on). Another card that reused the clone says it was withdrawn, can
    be answered again, and its video's voice is put back too. False: not a clone."""
    from app import director, voices
    from app.models.voices import Voice

    if ask.state != "answered" or (ask.answer or {}).get("how") != "clone":
        return False
    option = str(ask.answer["option"])
    voice = db.get(Voice, int(option.split(":")[1]))
    job = db.get(Job, voice.job_id) if voice and voice.job_id else None
    if job is None or job.status not in (JobStatus.queued, JobStatus.needs_owner_approval):
        raise HTTPException(409, STARTED)
    others: list[Ask] = []
    if user.is_owner or user.id == job.created_by_id:
        done = db.execute(update(Job).where(  # conditional: it can't race the worker
            Job.id == job.id, Job.status.in_((JobStatus.queued, JobStatus.needs_owner_approval))
        ).values(status=JobStatus.cancelled, finished_at=_now()))  # fmt: skip
        if done.rowcount != 1:
            raise HTTPException(409, STARTED)
        voices.withdrawn(voice, job)
        answered = select(Ask).where(Ask.id != ask.id, Ask.kind == "voice", Ask.state == "answered")
        same = {"how": "clone", "option": option}
        others = [a for a in db.scalars(answered) if same.items() <= (a.answer or {}).items()]
    elif user.id != ask.answered_by_id:
        raise HTTPException(403, NOT_YOURS)
    # else: a clone someone else asked for (reused by this card): the card opens again and
    # their clone goes on
    for other in others:  # it reused the withdrawn clone: says so, answerable again
        _unvoice(db, other)
        other.answer = {**other.answer, "withdrawn": True}
    _unvoice(db, ask)
    ask.state, ask.answer, ask.answered_by_id, ask.answered_at = "open", None, None, None
    db.commit()
    for project in {a.project_id for a in [ask, *others]}:  # each card is its director's question
        director.wake(db, db.get(Project, project))
    return True


def _unvoice(db: Session, ask: Ask) -> None:
    """The video's voice back to what it was before this card's clone answer set it (QA on
    #1353), with the answer's line taken out of the settings log so the earlier choice stands."""
    project, option = db.get(Project, ask.project_id), ask.answer["option"]
    if project.voice != option or ask.answer.get("before") == option:  # not this answer's doing
        return
    project.voice = ask.answer.get("before")
    log = list(project.settings_log or [])
    last = next((n for n in range(len(log) - 1, -1, -1) if log[n]["field"] == "voice"), None)
    if last is not None and log[last]["now"] == option:
        project.settings_log = log[:last] + log[last + 1 :]


def _cloned(db: Session, ask: Ask) -> str:
    """A voice card answered with a clone (#1314): being cloned ("held" while an editor's waits
    for the owner), answered once its voice is ready, failed when it didn't clone (nothing
    charged; the card can be answered again)."""
    from app import voices
    from app.models.voices import Voice

    voice = db.get(Voice, int(ask.answer["option"].split(":")[1]))
    said = voices.state(db, voice)[0] if voice else "failed"
    if said == "cloning":
        job = db.get(Job, voice.job_id) if voice.job_id else None
        return "held" if job and job.status == JobStatus.needs_owner_approval else "generating"
    return "answered" if said in ("ready", "may_expire") else "failed"


def _money_state(db: Session, ask: Ask) -> tuple[str, Job | None]:
    """A money card from its held jobs: open while any waits; answered once approved or
    declined (the job with who said so); not_needed when withdrawn, replaced or stopped."""
    from app.routes.jobs import DECLINE

    jobs = [j for j in db.scalars(select(Job).where(Job.id.in_(ask.job_ids or [0])))]
    if any(j.status == JobStatus.needs_owner_approval for j in jobs):
        return "open", None
    went = next((j for j in jobs if j.status != JobStatus.cancelled), None)
    no = next((j for j in jobs if j.input.get(DECLINE)), None)
    return ("answered", went or no) if went or no else ("not_needed", None)


def _money(db: Session, user: User, ask: Ask, project: Project, how: str) -> None:
    """A money card's press, checked whole before any job moves: Make it (the owner, or the
    video's editor on a run not held for the owner, inside what's left of its budget now),
    Approve, Keep it as it is or Decline (the owner), Withdraw (whoever asked: their own)."""
    from app.routes import jobs as routes

    held = [j for j in db.scalars(select(Job).where(Job.id.in_(ask.job_ids or [0])))
            if j.status == JobStatus.needs_owner_approval]  # fmt: skip
    if not held:
        raise HTTPException(409, NOT_WAITING)
    if how in ("make_it", "approve"):
        if not (user.is_owner or ask.kind == "start" and may_start(db, user, project)):
            raise HTTPException(403, "Only the owner can approve this.")
        if not user.is_owner and (why := start_hold(db, user, project)):
            held[-1].input = {**held[-1].input, HOLD: why, "held": why}  # the budget moved: to the
            db.commit()  # owner, saying why (rule 36: never less than it can charge)
            raise HTTPException(409, why)
        for job in held:
            routes.approve_job(job.id, user, db)
    elif how in ("keep", "decline"):
        if not user.is_owner:
            raise HTTPException(403, "Only the owner can decline this.")
        for job in held:
            routes.decline_job(job.id, routes.DeclineIn(reason=KEPT if how == "keep" else ""),
                               user, db)  # fmt: skip
        if ask.kind == "plan":  # the plan stays as it is: its start card comes back
            from app import director

            director.keep_plan(db, project, db.get(Job, held[0].id))
    elif how == "withdraw":
        mine = [j for j in held if user.is_owner or j.created_by_id == user.id]
        if not mine:
            raise HTTPException(403, "Only whoever asked can withdraw this.")
        for job in mine:
            routes.cancel_job(job.id, user, db)
    else:
        raise HTTPException(422, "That isn't a way to answer this card.")
    ask = db.get(Ask, ask.id)
    ask.answer, ask.answered_by_id, ask.answered_at = {"how": how}, user.id, _now()
    ask.state = _money_state(db, ask)[0]  # a withdraw leaves others' asks on it waiting
    db.commit()
    from app import director

    director.wake(db, project)


def may_start(db: Session, user: User, project: Project) -> bool:
    """Who presses Make it on a start card: the owner, or the editor whose video it is when
    its run wasn't held for the owner (a published library script inside what's left of its
    budget, S2-06). An editor's pasted words, New video or Freestyle send, or one past the
    budget waits for the owner (S4-02)."""
    if user.is_owner:
        return True
    card = _start_job(db, project)
    return bool(card) and project.created_by_id == user.id and not card.input.get(HOLD)


HOLD = "start_hold"  # in a start card's job: why it waits for the owner ("": its maker starts it)
CARRIES = "carries"  # in a start card for carrying a stopped run on: that run's approved price


def start_hold(db: Session, user: User, project: Project) -> str:
    """Why an editor's run on a published script waits for the owner at its start card: its
    whole "up to" is past what's left of the video's budget (Reed, 4 Nov); "" when it fits."""
    from app.credits import budget_used, price

    if user.is_owner:
        return ""
    left = project.budget_credits - budget_used(db, project)
    up_to = run_price(db, project)
    if up_to <= left:
        return ""
    return (f"Waiting for the owner's OK: up to {price(up_to)} credits is past what's left of "
            f"this video's budget ({price(max(left, Decimal(0)))}).")  # fmt: skip


def _start_job(db: Session, project: Project) -> Job | None:
    card = start_card(db, project)
    ask = db.get(Ask, card) if card else None
    return db.get(Job, ask.job_ids[-1]) if ask and ask.job_ids else None


PAST_PRICE = "past_price"  # in a held job: past the price its run's Make it approved


def approved_run(
    db: Session, project: Project, waiting: bool = False
) -> tuple[Decimal, Decimal] | None:
    """The video's newest run since its Make it: (the price approved, what the run has charged
    against it), or None before any Make it (rule 34: the owner's OK covers that price, no
    more; each OK at the director's own limit adds another limit's worth). What it charged is
    counted from its first turn, its planning before the OK included (QA on #1355: the price
    covers the run's turns), but not the steps the owner OK'd past that price nor planning OK'd
    at the planning cap: their own OKs cover those. `waiting`: a start card not pressed yet
    counts as the newest run too (what the header shows while it waits, never a hold)."""
    from app.credits import COUNTED
    from app.director import GRANT, RUN, own_limit

    states = (*COUNTED, JobStatus.needs_owner_approval) if waiting else COUNTED
    card = db.scalar(select(Job).where(
        Job.project_id == project.id, Job.input[START].as_boolean(), Job.status.in_(states))
        .order_by(Job.id.desc()).limit(1))  # fmt: skip
    if card is None or not Decimal(str(card.input.get("price") or 0)):
        return None
    run = (card.input.get(RUN) or {}).get("id")
    rows = db.scalars(select(Job).where(Job.project_id == project.id,
                                        Job.status.in_(COUNTED))).all()  # fmt: skip
    ours = (RUN, "by_director")  # its turns and its steps (a director's look's check too)
    mine = [j for j in rows if run and (j.input.get(RUN) or {}).get("id") == run
            or j.id >= card.id and any(j.input.get(k) for k in ours)]  # fmt: skip
    spent = sum((j.credits for j in mine if not j.input.get(PAST_PRICE)
                 and not j.input.get(PLAN_OK)), Decimal(0))  # fmt: skip
    oks = sum(1 for j in mine if j.input.get(GRANT))  # each OK at its own limit grants another
    if card.input.get(CARRIES):  # carrying a stopped run on: the run's own price, not the rest
        later = sum(1 for j in mine if j.id > card.id and j.input.get(GRANT))  # (its OKs till
        return Decimal(str(card.input[CARRIES])) + later * own_limit(), spent  # then are in it)
    return Decimal(str(card.input["price"])) + oks * own_limit(), spent


def approved_total(db: Session, project: Project) -> Decimal | None:
    """What every Make it on the video has approved (board S3-12: "up to $17.18" is the first
    run's $16.86 plus the change's $0.32): each start card's price, plus another of the
    director's own limit for each OK at it (rule 34), and a start card still waiting for its
    Make it at its price (S3-02: the header says the card's figure); None before any start
    card. The video's "up to" in its header, its run card and its note. `approved_run` is the
    newest run's own."""
    from app.credits import COUNTED
    from app.director import GRANT, own_limit

    rows = db.scalars(select(Job).where(
        Job.project_id == project.id,
        Job.status.in_((*COUNTED, JobStatus.needs_owner_approval)))).all()  # fmt: skip
    prices = [
        Decimal(str(j.input.get("price") or 0))
        for j in rows
        if j.input.get(START) and not j.input.get(CARRIES)
    ]  # a carried-on run's card: the same run's price
    if not any(prices):
        return None
    oks = sum(1 for j in rows if j.status in COUNTED and j.input.get(GRANT)
              and (j.input.get("director_run") or j.input.get("by_director")))  # fmt: skip
    return sum(prices, Decimal(0)) + oks * own_limit()


def past_run(db: Session, project: Project, credits: Decimal) -> bool:
    """Whether a run's step of `credits` would take it past the price its Make it approved:
    then it waits for the owner, the owner's own run too (Reed, 4 Nov)."""
    got = approved_run(db, project)
    return got is not None and got[1] + credits > got[0]


def planned(db: Session, project: Project) -> tuple[int, Decimal, int]:
    """The video's planning before Make it, as its allowance counts it: plans written (a
    check's own fix of one is the same plan), credits
    charged (actual usage, or the price while it runs) and the owner's OKs past it. Read from
    the video's own jobs since its last Make it, so a resend, reopen or refresh never resets
    it."""
    from app.credits import COUNTED

    anchor = db.scalar(select(func.max(Job.id)).where(
        Job.project_id == project.id, Job.input[START].as_boolean(),
        Job.status.in_(COUNTED)))  # fmt: skip
    rows = db.scalars(select(Job).where(Job.project_id == project.id, Job.id > (anchor or 0),
                                        Job.input[BEFORE].as_boolean(),
                                        Job.status.in_(COUNTED))).all()  # fmt: skip
    plans = sum(1 for j in rows if j.input.get("step") == "treatment" and not j.input.get("redo"))
    oks = sum(1 for j in rows if j.input.get(PLAN_OK))
    return plans, sum((j.credits for j in rows), Decimal(0)), oks


def past_planning(db: Session, project: Project, credits: Decimal, plan: bool) -> bool:
    """Whether one more planning job before Make it (`plan`: a treatment) would pass the
    video's allowance: the settings' plans and credits, whichever comes first; each owner's
    OK on a plan card lets one more plan through."""
    from app.settings import get_settings

    settings = get_settings()
    plans, used, oks = planned(db, project)
    cap = Decimal(str(settings.plan_credits_before_ok)) * (1 + oks)
    return used + credits > cap or plan and plans >= settings.plans_before_ok + oks


def run_price(db: Session, project: Project) -> Decimal:
    """The most a run on this video can charge (rule 34): `estimate.run_price`; a freestyle's
    video is held to the price its maker was quoted."""
    from app.models.script_library import ScriptDraft
    from app.routes.estimate import run_price as priced

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    return priced(db, draft, project) if draft else Decimal(0)


def held(db: Session, job: Job) -> None:
    """A job on a video was held for an OK: its money card, or the open budget card it joins
    ("Redo clips 9 and 12" is one card). An option's hold shows on its own question card."""
    if job.project_id is None or opts.ASK in job.input:
        return
    from app.credits import PAST_APPROVED

    kind = ("start" if job.input.get(START) else "plan" if job.input.get(PLAN_OK)
            else "own" if job.input.get("own_grant") else "budget")  # fmt: skip
    if kind == "budget" and job.input.get("held") == PAST_APPROVED:  # past the price approved:
        job.input = {**job.input, PAST_PRICE: True}  # its own OK covers it
    if kind == "budget":
        for ask in db.scalars(
            select(Ask).where(
                Ask.project_id == job.project_id, Ask.kind == kind, Ask.state == "open"
            )
        ):
            if _money_state(db, ask)[0] == "open":
                ask.job_ids = [*ask.job_ids, job.id]
                return
    run = (job.input.get("director_run") or {}).get("id")
    db.add(Ask(workspace_id=job.workspace_id, project_id=job.project_id, run=run, kind=kind,
               job_ids=[job.id]))  # fmt: skip


def sync(db: Session, ask: Ask) -> str:
    """A card's state now, kept on the row for money cards answered through the job routes."""
    now = state(db, ask)
    if ask.kind in MONEY and now != "open" and ask.state == "open":
        ask.state = now
    return now


# --- What the director and the lists read -----------------------------------------------------


def waiting(db: Session, project: Project) -> list[Ask]:
    """The video's open questions, oldest first (the pinned bar, S4-03)."""
    rows = db.scalars(select(Ask).where(Ask.project_id == project.id, Ask.kind.in_(QUESTIONS),
                                        Ask.state.in_(OPEN)).order_by(Ask.id)).all()  # fmt: skip
    return list(rows)


def start_card(db: Session, project: Project) -> int | None:
    """The video's start card while it waits for Make it (S3-02), else None."""
    rows = db.scalars(select(Ask).where(Ask.project_id == project.id, Ask.kind == "start",
                                        Ask.state == "open").order_by(Ask.id.desc()))  # fmt: skip
    return next((a.id for a in rows if state(db, a) == "open"), None)


def starting(db: Session, ids: list[int]) -> set[int]:
    """The videos whose start card waits for Make it."""
    rows = db.scalars(select(Ask).where(Ask.project_id.in_(ids), Ask.kind == "start",
                                        Ask.state == "open"))  # fmt: skip
    return {a.project_id for a in rows if state(db, a) == "open"}


def card_price(db: Session, ask_id: int) -> float | None:
    """A start card's own "up to", in credits, as the card shows it (never below the charge)."""
    from app.credits import price

    ask = db.get(Ask, ask_id)
    job = db.get(Job, ask.job_ids[-1]) if ask and ask.job_ids else None
    return price(Decimal(str(job.input["price"]))) if job and job.input.get("price") else None


def needing(db: Session, ids: list[int]) -> dict[int, str]:
    """Video id -> its first open question, for the idea's "Needs you" and its reason (the
    folder tree, S-gaps-01 option 4)."""
    rows = db.scalars(select(Ask).where(Ask.project_id.in_(ids), Ask.kind.in_(QUESTIONS),
                                        Ask.state.in_(OPEN)).order_by(Ask.id)).all()  # fmt: skip
    out: dict[int, str] = {}
    for ask in rows:
        out.setdefault(ask.project_id, ask.question)
    return out


def answered_since(db: Session, project: Project, at: str) -> bool:
    """Whether a question on the video was answered (or closed) after `at` (ISO)."""
    rows = db.scalars(select(Ask.answered_at).where(Ask.project_id == project.id,
                                                    Ask.answered_at.is_not(None)))  # fmt: skip
    return any(t.isoformat() > at for t in rows)


def for_director(db: Session, project: Project) -> list[dict]:
    """<asks> in the director's turn: each question, its state and the answer as it reads
    (a picture by its number in <seen>), newest 12."""
    from app.auth import user_name

    rows = db.scalars(select(Ask).where(Ask.project_id == project.id, Ask.kind.in_(QUESTIONS))
                      .order_by(Ask.id.desc()).limit(12)).all()  # fmt: skip
    out = []
    for ask in reversed(rows):
        data = ask.answer or {}
        said = ("" if not data else f"no answer by the time on the card: your pick {data['name']}"
                if data.get("how") == "default" else
                data.get("text") or data.get("name") or "")  # fmt: skip
        out.append({"ask_id": ask.id, "kind": ask.kind, "topic": ask.topic,
                    "question": ask.question, "state": state(db, ask), "answer": said,
                    "how": data.get("how"), "picture": bool(data.get("file_id")),
                    "by": user_name(db, ask.answered_by_id) if ask.answered_by_id else "",
                    "closed": ask.closed})  # fmt: skip
    return out


def seen(db: Session, project: Project) -> list[tuple[str, int, bool]]:
    """What the director looks at in its turn: each picture or clip given for this video
    (answers, the chat's uploads, New video's attachments), as (label, file id, is a clip)."""
    from app.models.files import StoredFile

    given = [(f"your answer to “{a.question}”", a.answer["file_id"])
             for a in db.scalars(select(Ask).where(Ask.project_id == project.id,
                                                   Ask.state == "answered").order_by(Ask.id))
             if (a.answer or {}).get("file_id")]  # fmt: skip
    given += [(f"sent in the chat: “{m['text'][:80]}”", f)
              for m in project.director_chat or [] for f in m.get("files") or []]  # fmt: skip
    given += [("attached in New video", f) for f in project.attachments or []]
    from app.routes.reel_video import look_reference

    if sheet := (look_reference(db, project) or {}).get("contact_sheet_file_id"):
        given.append(("the reel's contact sheet: follow its look, never its story", sheet))
    out = []
    for label, file_id in given:
        stored = db.get(StoredFile, file_id)
        kind = stored.content_type.split("/")[0] if stored else ""
        if kind in ("image", "video") and all(file_id != o[1] for o in out):
            out.append((label, file_id, kind == "video"))
    return out[-12:]


def overdue(db: Session) -> list[int]:
    """Story choices past their time: the director's pick is taken (rule 37). The videos."""
    rows = db.scalars(select(Ask).where(Ask.kind == "story", Ask.state == "open",
                                        Ask.decide_at <= _now())).all()  # fmt: skip
    for ask in rows:
        found = next((c for c in ask.choices if c["key"] == ask.pick), ask.choices[0])
        ask.state, ask.answered_at = "answered", _now()
        ask.answer = {"how": "default", "choice": found["key"], "name": found["title"]}
    db.commit()
    return sorted({a.project_id for a in rows})


def close_run(db: Session, run_id: str, why: str) -> None:
    """A run that ends leaves its open questions no longer needed, saying why."""
    for ask in db.scalars(select(Ask).where(Ask.run == run_id, Ask.kind.in_(QUESTIONS),
                                            Ask.state.in_(OPEN))):  # fmt: skip
        ask.state, ask.closed = "not_needed", why
        opts.stop_options(db, ask)
