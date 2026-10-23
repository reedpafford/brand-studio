"""App factory. Run with: uvicorn app.main:create_app --factory"""

from fastapi import FastAPI

from app.db import make_sessionmaker
from app.routes import auth, brands, files, health, library, screens, team
from app.settings import Settings, get_settings
from app.storage import LocalStorage
from app.upload_limit import UploadLimit


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Brand Studio API", version="0.1.0")
    app.state.settings = settings
    app.state.sessionmaker = make_sessionmaker(settings.database_url)
    app.state.storage = LocalStorage(settings.storage_dir)
    for module in (health, auth, team, files, brands, screens, library):
        app.include_router(module.router)
    app.add_middleware(UploadLimit, path="/files", max_bytes=settings.max_upload_mb * 1024 * 1024)
    return app
