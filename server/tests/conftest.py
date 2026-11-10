import atexit
import io
import ipaddress
import os
import shutil
import socket
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

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
    test site has real lanes (Suno, look samples, the language test). With every key empty no
    real provider can be called; empty keys beat a .env file (pydantic-settings reads
    environment variables first). Settings are only read when a test makes them, so this runs
    before any are. The stand-in switch is left to each test: some test the real paths' rules."""
    for key in ("STUDIO_ANTHROPIC_KEY", "REPLICATE_API_TOKEN", "KIE_API_KEY"):
        os.environ[key] = ""
    # The tests' owner is held as the team is, so the team's holds stay tested through either
    # account; tests/test_owner_uncapped.py turns the owner's no-hold mode (the sites' own) on.
    os.environ["BS_OWNER_UNCAPPED"] = "false"
    # Passwords hash with argon2's lightest settings here: every test signs people up and in,
    # and the real settings are built to be slow (the hash and its check are the same code).
    from argon2 import PasswordHasher

    from app import auth

    auth._hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    # The stand-ins' grey pictures and clips at half size: the same code runs on them, with a
    # quarter of the pixels for every cut to encode (most of a long test's time is ffmpeg).
    from app.providers import fake_local

    fake_local.SIZES = {shape: (w // 2, h // 2) for shape, (w, h) in fake_local.SIZES.items()}
    # An empty key isn't enough on its own: with no token the Replicate provider sends its
    # request bare, and a sandbox's network proxy adds real credentials. So no test may open
    # a connection off this machine at all; tests talk to fakes or local servers only.
    # The sandbox's proxy runs on this machine and signs what it forwards, so its address is
    # refused too, and the proxy settings are cleared so nothing even tries it.
    for name in (
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "all_proxy",
    ):
        proxy = urlsplit(os.environ.pop(name, "") or "")
        if proxy.hostname and proxy.port:
            _PROXIES.add((proxy.hostname, proxy.port))
    socket.socket.connect = _local_only(socket.socket.connect)
    socket.socket.connect_ex = _local_only(socket.socket.connect_ex)


_PROXIES: set[tuple[str, int]] = set()


class OffMachine(RuntimeError):
    """A test tried to reach the network: it must use a fake or a mock transport instead."""


def _local_only(connect):
    def guarded(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            host = address[0]
            try:
                local = host == "localhost" or ipaddress.ip_address(host).is_loopback
            except ValueError:
                local = False
            if not local or (host, address[1]) in _PROXIES:
                raise OffMachine(f"Tests never reach the network (tried {host}).")
        return connect(sock, address)

    return guarded


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


_SAVED: dict[str, tuple] = {}


def saved(app, db, module: str, make, *clients):
    """A slow setup (a whole director run, say) made once per test process, then copied. The
    first test to ask runs `make()` and keeps the database, the files and `clients`' sign-ins as
    they stand after it; each later one starting from the same rows gets a copy of them, and
    `make`'s answer (plain data, such as an id), instead. Only for a setup whose whole effect is
    in the database, the files and those sign-ins (no patching or settings changes inside), and
    only in `module`, the one that checked its tests for that: a test elsewhere, or one that
    added rows first (a second setup, say), is made for real. The module is one xdist_group, so
    a test process makes it once (`--dist loadgroup`)."""
    path = app.state.sessionmaker.kw["bind"].url.database
    files = Path(app.state.settings.storage_dir)
    here = os.environ["PYTEST_CURRENT_TEST"].split("::")[0] == module.replace(".", "/") + ".py"
    if not here or (module in _SAVED and _SAVED[module][0] != _rows(path)):
        return make()
    if module not in _SAVED:
        before = _rows(path)
        answer = make()
        keep = Path(tempfile.mkdtemp(prefix="bs-saved-"))
        atexit.register(shutil.rmtree, keep, True)
        _copy_db(path, str(keep / "test.db"))
        files.mkdir(parents=True, exist_ok=True)
        shutil.copytree(files, keep / "files")
        _SAVED[module] = (before, keep, [list(c.cookies.jar) for c in clients], answer)
        return answer
    _, keep, jars, answer = _SAVED[module]
    db.close()
    _copy_db(str(keep / "test.db"), path)
    shutil.rmtree(files, ignore_errors=True)
    shutil.copytree(keep / "files", files)
    for c, jar in zip(clients, jars, strict=True):
        c.cookies.jar.clear()
        for cookie in jar:
            c.cookies.jar.set_cookie(cookie)
    return answer


def _rows(path: str) -> dict[str, int]:
    """How many rows each table holds."""
    with closing(sqlite3.connect(path)) as c:
        tables = [t for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        return {t: c.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in tables}  # noqa: S608


def _copy_db(src: str, dst: str) -> None:
    with closing(sqlite3.connect(src)) as a, closing(sqlite3.connect(dst)) as b:
        a.backup(b)


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


# Shared helpers (each was copied between test files)


def run_writer(app, db) -> None:
    """Run the waiting Claude jobs once, on the free stand-in writer."""
    from app.providers.fake_local import FakeWriter
    from app.worker import run_once

    run_once(db, {"claude": FakeWriter()}, app.state.storage, only={"claude"})


def first_brand(client) -> int:
    """The workspace's first brand (fomo, from setup)."""
    return client.get("/brands").json()[0]["id"]


def file_into(client, kind, item_id, folder_id):
    """File a script, video or quick clip into a folder (OR1)."""
    body = {"kind": kind, "ids": [item_id], "folder_id": folder_id}
    return client.post("/folders/file", json=body)


def bulk_scripts(client, rows: list[dict]):
    """Create several scripts at once, all in the first brand."""
    brand = first_brand(client)
    return client.post("/scripts/bulk", json={"scripts": [{"brand_id": brand, **r} for r in rows]})


@pytest.fixture
def own_look(monkeypatch):
    """A video that keeps no script's style (one made the earlier way), so its own look can
    switch (VS1, n12): the switch tests run on a script's video, which keeps its style now."""
    monkeypatch.setattr("app.looks.script_style", lambda db, project: None)


@pytest.fixture
def heygen_talker(monkeypatch):
    """A presenter who talks to camera on HeyGen, in their own room over our voice track (as
    one does outside UGC): the UGC look's stand-in plans talker shots for it, but a UGC talker
    on camera is filmed on Omni now (app/omni_talker.on, tests/test_omni_talker.py)."""
    monkeypatch.setattr("app.omni_talker.full_screen", lambda look, presenter: False)


def make_cut(app, db, client, base: str):
    """Make the cut (POST /projects/N/cut) and run the local lane once, as the worker would:
    GET …/video after, or POST's own answer when it was refused."""
    from app.providers.local import LocalProvider
    from app.worker import run_once

    asked = client.post(f"{base}/cut")
    if asked.status_code != 202:
        return asked
    run_once(db, {"local": LocalProvider(app.state.storage)}, app.state.storage, only={"local"})
    db.expire_all()
    return client.get(f"{base}/video")


@pytest.fixture(autouse=True)
def _style_voices_just_cloned(monkeypatch):
    """A style's own cloned voice (Dr. Pickle) is seeded with the day it was really cloned
    (3 Nov), and a clone unused for 7 days reads as expired: from 10 Nov every test that meets
    the voice in a fresh workspace failed on the calendar. In tests it was cloned now; a test of
    expiry sets `last_used_at` itself."""
    from app import voices
    from app.db import utcnow

    fresh = tuple({**v, "cloned_at": utcnow().isoformat()} for v in voices.STYLE_VOICES)
    monkeypatch.setattr(voices, "STYLE_VOICES", fresh)
