"""Refuse oversize uploads from their Content-Length, before the body is read."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

ENVELOPE = 1024 * 1024  # allowance for the multipart wrapping around the file


class UploadLimit:
    def __init__(self, app: ASGIApp, path: str, max_bytes: int):
        self.app, self.path, self.max_bytes = app, path, max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] == self.path:
            headers = dict(scope["headers"])
            length = headers.get(b"content-length")
            if length is None:
                await JSONResponse({"detail": "Content-Length is required."}, 411)(
                    scope, receive, send
                )
                return
            if not length.isdigit() or int(length) > self.max_bytes + ENVELOPE:
                await JSONResponse({"detail": "That file is too big."}, 413)(scope, receive, send)
                return
        await self.app(scope, receive, send)
