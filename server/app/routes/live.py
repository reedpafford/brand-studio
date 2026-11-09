"""A video page's push updates (app/live.py): one server-sent events stream per open video."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.auth import current_user
from app.live import BYE
from app.routes.projects import get_project

router = APIRouter(tags=["live"])
STILL_HERE = 15  # seconds: a quiet stream says so; a page hearing nothing for 45 s reconnects
LIFETIME = 600  # seconds: then the page opens a new stream at once, and who may read is asked again


def _may_read(request: Request, project_id: int) -> None:
    # Its own session, closed before the stream starts: an open page holds no database connection
    with request.app.state.sessionmaker() as db:
        get_project(db, current_user(request, db), project_id)


@router.get("/projects/{project_id}/live", response_class=StreamingResponse)
async def live(project_id: int, request: Request):
    """Whoever may read the video hears, as each change lands, which part of it changed: `data:
    jobs | made | cards | video` (app/live.py). Never the change itself: the page reads it.
    `event: still` every 15 s while nothing changes; `event: bye` when the stream ends."""
    await run_in_threadpool(_may_read, request, project_id)
    hub = request.app.state.live

    async def events():
        page = hub.join(project_id)
        try:
            for _ in range(500):  # the page hears it open once nothing can be missed (5 s at most)
                if hub.ready.is_set():
                    break
                await asyncio.sleep(0.01)
            yield "retry: 2000\n\n"
            end = asyncio.get_running_loop().time() + LIFETIME
            while (left := end - asyncio.get_running_loop().time()) > 0:
                try:
                    kind = await asyncio.wait_for(page[1].get(), min(STILL_HERE, left))
                except TimeoutError:
                    yield "event: still\ndata: here\n\n"
                    continue
                if kind == BYE:
                    break
                yield f"data: {kind}\n\n"
            yield f"event: {BYE}\ndata: {BYE}\n\n"
        finally:
            hub.leave(project_id, page)

    # no-transform: Caddy never compresses it, so each line goes out the moment it's written
    headers = {"Cache-Control": "no-cache, no-transform"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)
