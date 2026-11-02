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
