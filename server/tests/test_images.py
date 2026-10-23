"""Nano Banana job input (FIT.md rows 5, 6, 24). No real or paid calls."""

import json

import httpx2 as httpx
import pytest
from fastapi import HTTPException

from app.catalogue import get_model
from app.images import image_job_input, image_model_block
from app.models.accounts import Role, User
from app.providers.replicate import ReplicateProvider
from app.routes.jobs import enqueue
from app.worker import run_once
from tests.conftest import upload
from tests.test_replicate import BASE, FakeReplicate

NB, PRO = get_model("nano-banana-2.1"), get_model("nano-banana-pro")


@pytest.mark.parametrize("model", [NB, PRO])
def test_always_sends_aspect_and_never_the_fallback(app, editor, db, model):
    sheet = upload(editor)
    ed = db.query(User).filter_by(role=Role.editor).one()
    job_input = image_job_input(model, "Generate a still of Max", "9:16", characters=[sheet])
    enqueue(db, ed, "image", job_input, provider="replicate")
    fake = FakeReplicate()
    run_once(
        db,
        {"replicate": ReplicateProvider(BASE, httpx.Client(transport=httpx.MockTransport(fake)))},
        app.state.storage,
    )
    sent = json.loads(next(q for q in fake.requests if q.method == "POST").content)["input"]
    assert sent["aspect_ratio"] == "9:16"
    assert sent.get("allow_fallback_model", False) is False  # Pro: sent as false
    assert ("allow_fallback_model" in sent) == (model is PRO)
    assert sent["image_input"][0].startswith("data:image/png;base64,")


def test_aspect_and_resolution_are_checked():
    with pytest.raises(HTTPException):
        image_job_input(NB, "x", "match_input_image")
    with pytest.raises(HTTPException) as err:
        image_job_input(NB, "x", "9:16", resolution="8K")
    assert err.value.detail == "Nano Banana 2.1 offers 1K, 2K, 4K."


def test_character_likeness_limits():
    assert (NB.max_character_images, NB.max_object_images, PRO.max_character_images) == (4, 10, 5)
    image_job_input(NB, "x", "9:16", characters=[1, 2, 3, 4], objects=list(range(5, 15)))
    with pytest.raises(HTTPException) as err:
        image_job_input(NB, "x", "9:16", characters=[1, 2, 3, 4, 5])
    assert err.value.detail == (
        "Nano Banana 2.1 keeps likeness for up to 4 character sheets; this has 5."
    )
    image_job_input(PRO, "x", "9:16", characters=[1, 2, 3, 4, 5])
    assert "max character sheets: 4\nmax other references: 10" in image_model_block(NB, "9:16")
