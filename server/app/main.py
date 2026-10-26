"""App factory. Run with: uvicorn app.main:create_app --factory"""

from fastapi import FastAPI

from app.db import make_sessionmaker
from app.routes import (
    auth,
    brands,
    breakdown,
    clips,
    clips_zip,
    credits,
    drafts,
    enhance,
    estimate,
    files,
    health,
    improve,
    jobs,
    library,
    models,
    production,
    project_assets,
    project_clips,
    projects,
    references,
    screens,
    script_cast,
    script_cast_read,
    script_import,
    script_library,
    script_preview,
    script_produce,
    script_variations,
    script_write,
    scripts,
    sheets,
    storyboard,
    team,
    usage,
)
from app.routes.scripts import MAX_DOC_BYTES
from app.settings import Settings, check_production, get_settings
from app.storage import LocalStorage
from app.upload_limit import UploadLimit


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    check_production(settings)
    app = FastAPI(title="Brand Studio API", version="0.1.0")
    app.state.settings = settings
    app.state.sessionmaker = make_sessionmaker(settings.database_url)
    app.state.storage = LocalStorage(settings.storage_dir)
    for module in (
        health,
        auth,
        team,
        files,
        brands,
        screens,
        library,
        sheets,
        jobs,
        usage,
        production,
        projects,
        credits,
        estimate,
        models,
        references,
        scripts,
        script_write,
        script_import,
        script_library,
        script_cast_read,
        script_cast,
        script_preview,
        script_produce,
        script_variations,
        enhance,
        drafts,
        breakdown,
        storyboard,
        project_clips,
        clips_zip,
        project_assets,
        improve,
        clips,
    ):
        app.include_router(module.router)
    app.add_middleware(UploadLimit, path="/files", max_bytes=settings.max_upload_mb * 1024 * 1024)
    app.add_middleware(UploadLimit, path=r"/projects/\d+/script/upload", max_bytes=MAX_DOC_BYTES)
    app.add_middleware(
        UploadLimit, path=script_import.UPLOAD_PATHS, max_bytes=script_import.MAX_BYTES
    )
    return app
