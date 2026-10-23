import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.db import Base
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def app(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path}/test.db")
    application = create_app(settings)
    Base.metadata.create_all(application.state.sessionmaker.kw["bind"])
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(app):
    with app.state.sessionmaker() as session:
        yield session
