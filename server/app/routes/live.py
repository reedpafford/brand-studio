"""A video page's push updates (app/live.py): one server-sent events stream per open video."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.auth import current_user
from app.routes.projects import get_project

router = APIRouter(tags=["live"])
STILL_HERE = 20  # seconds: a quiet stream says so this often, so nothing on the way closes it
LIFETIME = 600  # seconds: then the page opens a new stream at once, and who may read is asked again


def _may_read(request: Request, project_id: int) -> None:
    # Its own session, closed before the stream starts: an open page holds no database connection
    with request.app.state.sessionmaker() as db:
        get_project(db, current_user(request, db), project_id)


@router.get("/projects/{project_id}/live", response_class=StreamingResponse)
async def live(project_id: int, request: Request):
    """Whoever may read the video hears, as each change lands, which part of it changed: `data:
    jobs | made | cards | video` (app/live.py). Never the change itself: the page reads it."""
    await run_in_threadpool(_may_read, request, project_id)
    hub = request.app.state.live

    async def events():
        page = hub.join(project_id)
        try:
            yield "retry: 2000\n\n"
            end = asyncio.get_running_loop().time() + LIFETIME
            while (left := end - asyncio.get_running_loop().time()) > 0:
                try:
                    kind = await asyncio.wait_for(page[1].get(), min(STILL_HERE, left))
                    yield f"data: {kind}\n\n"
                except TimeoutError:
                    yield ": still here\n\n"
            yield "event: bye\ndata: bye\n\n"
        finally:
            hub.leave(project_id, page)

    # no-transform: Caddy never compresses it, so each line goes out the moment it's written
    headers = {"Cache-Control": "no-cache, no-transform"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)
