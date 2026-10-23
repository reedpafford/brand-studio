"""App factory. Run with: uvicorn app.main:create_app --factory"""

from fastapi import FastAPI

from app.db import make_sessionmaker
from app.routes import auth, files, health, team
from app.settings import Settings, get_settings
from app.storage import LocalStorage


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Brand Studio API", version="0.1.0")
    app.state.settings = settings
    app.state.sessionmaker = make_sessionmaker(settings.database_url)
    app.state.storage = LocalStorage(settings.storage_dir)
    for module in (health, auth, team, files):
        app.include_router(module.router)
    return app
