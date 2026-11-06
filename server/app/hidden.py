"""Hidden rows (Freestyle 3a): a freestyle's own script, video and, with no brand picked, the
workspace's "Freestyle" brand are real rows the director works on, but nobody sees them as
such: not in Scripts, Videos, In production, Needs you's videos, the brand menu, Usage's brand
rows or any count. One filter does it, for every query on every session: a hidden row is left
out unless the session is marked to see them (`see`): the worker, and Freestyle's own routes
and the job presses (approve, decline, cancel) that act on its jobs; or one query asks
(execution option `SEE`), as Usage's Freestyle figure does."""

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

SEE = "see_hidden"  # in Session.info: this session works on hidden rows too


def see(db: Session) -> Session:
    db.info[SEE] = True
    return db


@event.listens_for(Session, "do_orm_execute")
def _leave_out(state) -> None:
    if not state.is_select or state.session.info.get(SEE) or state.execution_options.get(SEE):
        return
    from app.models.brands import Brand
    from app.models.projects import Project
    from app.models.script_library import Script

    state.statement = state.statement.options(
        *(
            with_loader_criteria(m, m.hidden.is_(False), include_aliases=True)
            for m in (Project, Script, Brand)
        )  # fmt: skip
    )


def held_sends(db: Session, user, brand_id: int | None = None, project_id: int | None = None):
    """An editor's sends waiting for the owner's OK (S2-04, S3-07): their videos stay out of
    every list and count (Freestyle 3a), but whoever sent one and the owner see it in the tree
    and open it while any job of its waits for the OK or is on its way to it (its start card;
    the director's turns after the owner's note, QA on #1380). Declined or withdrawn, nothing
    is left of it. The videos, newest first."""
    from sqlalchemy import select

    from app.models.jobs import Job, JobStatus
    from app.models.projects import Project

    waits = (JobStatus.needs_owner_approval, JobStatus.queued, JobStatus.running)
    query = select(Project).join(Job, Job.project_id == Project.id).where(
        Project.workspace_id == user.workspace_id, Project.hidden,
        Project.archived_at.is_(None), Job.status.in_(waits))  # fmt: skip
    if not user.is_owner:
        query = query.where(Project.created_by_id == user.id)
    if brand_id is not None:
        query = query.where(Project.brand_id == brand_id)
    if project_id is not None:
        query = query.where(Project.id == project_id)
    return list(db.scalars(query.order_by(Project.id.desc()).execution_options(**{SEE: True}))
                .unique())  # fmt: skip
