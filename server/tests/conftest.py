import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app.models  # noqa: F401
from app.auth import hash_password
from app.db import Base
from app.main import create_app
from app.models.accounts import Role, User, Workspace
from app.settings import Settings

SETUP_TOKEN = "test-setup-token"
PASSWORD = "correct horse battery"


def pytest_configure(config):
    """No test may reach a paid service: tester and CI machines can hold real keys, and the
    test site has real lanes (Suno, look samples, the language test). Empty keys beat a .env
    file (pydantic-settings reads environment variables first), and the stand-ins are on.
    Settings are only read when a test makes them, so this runs before any are."""
    for key in ("STUDIO_ANTHROPIC_KEY", "REPLICATE_API_TOKEN", "KIE_API_KEY"):
        os.environ[key] = ""
    os.environ["BS_FAKE_PROVIDERS"] = "true"


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/test.db",
        storage_dir=str(tmp_path / "files"),
        brand_assets_dir="",
        generation_enabled=True,
        cookie_secure=False,
        setup_token=SETUP_TOKEN,
    )
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


@pytest.fixture
def owner(client):
    """`client`, logged in as the workspace owner."""
    r = client.post(
        "/auth/setup",
        json={
            "setup_token": SETUP_TOKEN,
            "workspace_name": "Studio",
            "email": "reed@example.com",
            "name": "Reed",
            "password": PASSWORD,
        },
    )
    assert r.status_code == 201, r.text
    return client


@pytest.fixture
def editor(app, owner):
    """A second client, logged in as an editor invited by the owner."""
    token = owner.post("/team/invites", json={"email": "ed@example.com"}).json()["token"]
    with TestClient(app) as c:
        r = c.post("/auth/accept-invite", json={"token": token, "name": "Ed", "password": PASSWORD})
        assert r.status_code == 201, r.text
        yield c


def png(width: int = 2, height: int = 2, color: str | tuple = "orange") -> bytes:
    out = io.BytesIO()
    Image.new("RGBA" if isinstance(color, tuple) else "RGB", (width, height), color).save(
        out, "PNG"
    )
    return out.getvalue()


PNG = png()


def upload(client, name="a.png", data=PNG, content_type="image/png") -> int:
    r = client.post("/files", files={"upload": (name, data, content_type)})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def outsider(app, db, owner):
    """A client logged in as the owner of a *different* workspace (inserted directly,
    since setup only allows one)."""
    db.add(
        User(
            workspace=Workspace(name="Other"),
            email="other@example.com",
            name="Other",
            password_hash=hash_password(PASSWORD),
            role=Role.owner,
        )
    )
    db.commit()
    with TestClient(app) as c:
        r = c.post("/auth/login", json={"email": "other@example.com", "password": PASSWORD})
        assert r.status_code == 200, r.text
        yield c
