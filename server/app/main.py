"""App factory. Run with: uvicorn app.main:create_app --factory"""

from fastapi import FastAPI

from app import advice
from app.db import make_sessionmaker
from app.live import Hub
from app.routes import (
    asks,
    auth,
    brands,
    breakdown,
    cast,
    checks,
    clips,
    clips_zip,
    credits,
    cut,
    director,
    draft_plan,
    drafts,
    enhance,
    estimate,
    files,
    folders,
    footage,
    freestyles,
    health,
    host,
    improve,
    jobs,
    languages,
    library,
    live,
    locks,
    looks,
    media,
    models,
    needs_you,
    plan,
    production,
    project_assets,
    project_clips,
    projects,
    reel_breakdown,
    reel_video,
    references,
    scorecard,
    screens,
    script_cast,
    script_cast_read,
    script_enhance,
    script_import,
    script_library,
    script_preview,
    script_produce,
    script_variations,
    script_write,
    scripts,
    sheets,
    song_study,
    songs,
    spend,
    storyboard,
    take_sound,
    team,
    update_after,
    uploads,
    usage,
    variations,
    video_settings,
    voices,
    workspace,
)
from app.routes.scripts import MAX_DOC_BYTES
from app.settings import Settings, check_production, get_settings
from app.storage import LocalStorage
from app.upload_limit import UploadLimit


class Requester:
    """One holder per request for who's asking (advice.REQUEST), so a message in the reply
    only ever names things from the asker's own workspace."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        token = advice.REQUEST.set({}) if scope["type"] == "http" else None
        try:
            await self.app(scope, receive, send)
        finally:
            if token is not None:
                advice.REQUEST.reset(token)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    check_production(settings)
    app = FastAPI(title="Brand Studio API", version="0.1.0")
    app.state.settings = settings
    app.state.sessionmaker = make_sessionmaker(settings.database_url)
    app.state.live = Hub(settings.database_url)  # its open video pages (app/live.py)
    advice.LOOKUP = app.state.sessionmaker  # names an id left in a shown message
    app.state.storage = LocalStorage(settings.storage_dir)
    for module in (
        health,
        auth,
        team,
        workspace,
        files,
        folders,
        reel_video,  # /freestyles/reel, ahead of /freestyles/{id}
        freestyles,
        brands,
        screens,
        library,
        footage,
        locks,
        sheets,
        jobs,
        asks,
        needs_you,
        usage,
        spend,
        scorecard,
        production,
        projects,
        credits,
        estimate,
        models,
        reel_breakdown,
        references,
        scripts,
        script_write,
        script_import,
        uploads,
        script_library,
        script_cast_read,
        script_cast,
        script_preview,
        script_produce,
        script_variations,
        script_enhance,
        enhance,
        drafts,
        breakdown,
        storyboard,
        project_clips,
        take_sound,
        cut,
        host,
        director,
        variations,
        update_after,
        clips_zip,
        project_assets,
        cast,
        improve,
        clips,
        songs,
        looks,
        song_study,
        plan,
        checks,
        draft_plan,
        video_settings,
        languages,
        media,
        voices,
        live,
    ):
        app.include_router(module.router)
    app.include_router(breakdown.shots)
    app.include_router(director.watched)
    app.include_router(looks.formats)
    app.include_router(looks.cards)
    app.include_router(host.ways)
    app.add_middleware(UploadLimit, path="/files", max_bytes=settings.max_upload_mb * 1024 * 1024)
    app.add_middleware(UploadLimit, path=r"/brands/\d+/(media|footage)",
                       max_bytes=settings.max_upload_mb * 1024 * 1024)  # fmt: skip
    app.add_middleware(UploadLimit, path=r"/projects/\d+/script/upload", max_bytes=MAX_DOC_BYTES)
    app.add_middleware(
        UploadLimit, path=script_import.UPLOAD_PATHS, max_bytes=script_import.MAX_BYTES
    )
    app.add_middleware(Requester)
    return app
