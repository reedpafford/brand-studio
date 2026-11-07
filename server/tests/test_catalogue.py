import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.catalogue import catalogue, get_model
from tests.helpers import assert_no_dollars

FIXTURES = Path(__file__).parent / "fixtures" / "replicate"


def _schema(model):
    return json.loads((FIXTURES / (model.provider_model.replace("/", "_") + ".json")).read_text())


def _enum(schema, field):
    prop = schema["Input"]["properties"][field]
    if "enum" in prop:  # a dereferenced schema (P-Video's) has it in place
        return prop["enum"]
    return schema["enums"][prop["allOf"][0]["$ref"].split("/")[-1]]["enum"]


def _up_to(schema, field) -> int:
    text = schema["Input"]["properties"][field]["description"]
    found = re.search(r"(?:up to|max) (\d+)|\(\d+-(\d+) ", text)  # Seedance 1 Lite: "(1-4 images)"
    return int(found.group(1) or found.group(2)) if found else None  # Omni's states none


@pytest.mark.parametrize("model", catalogue().values(), ids=lambda m: m.id)
def test_limits_match_replicate_schema(model):
    """Every limit in the catalogue is checked against the recorded Replicate schema."""
    schema = _schema(model)
    props = schema["Input"]["properties"]
    assert model.provider_version == schema["version"]
    if model.resolutions:
        assert set(model.resolutions) <= set(_enum(schema, "resolution"))
    if model.aspect_ratios:
        assert set(model.aspect_ratios) <= set(_enum(schema, "aspect_ratio"))
    if model.duration:
        assert model.duration.max == props["duration"]["maximum"]
        assert model.duration.smart == (props["duration"]["minimum"] == -1)
    opening = "image" in props and model.kind == "video"  # MMAudio's `image` is a sound's source
    images = "reference_images" if "reference_images" in props else None
    images = images or ("image_input" if "image_input" in props else "images")
    if images in props:
        stated = _up_to(schema, images)
        assert model.max_reference_images == stated if stated else model.max_reference_images
    else:  # speech: no pictures; P-Video: its one `image`, the opening frame
        assert model.max_reference_images == int(opening)
    for kind in ("videos", "audios"):
        field = f"reference_{kind}" if f"reference_{kind}" in props else kind
        if field in props:
            assert getattr(model, f"max_reference_{kind}") == _up_to(schema, field)
    assert model.first_frame == opening
    assert model.last_frame == ("last_frame_image" in props)
    assert (model.audio == "switch") == ("generate_audio" in props)


def test_credit_rates_follow_real_price():
    seedance = get_model("seedance-2.5")
    assert seedance.credits_per_unit("480p") == 1
    assert seedance.credits_per_unit("720p") == 2.25
    with pytest.raises(ValueError):
        seedance.credits_per_unit("1080p")


def test_p_video_is_in_the_pickers_at_720p_and_its_real_cost(editor):
    """Reed, 2026-11-03: "Unlock p-video at 720p, it is still only $.02 a second." It has no
    480p, so its takes are made at its lowest, 720p; it lip-syncs to audio it is given."""
    p_video = get_model("p-video")
    assert p_video.usd_per_unit("720p") == Decimal("0.02")
    assert p_video.credits_per_unit("720p") == Decimal("0.19")
    assert (p_video.take_resolution, p_video.lip_sync) == ("720p", True)
    shown = {m["id"]: m for m in editor.get("/models").json()}
    assert shown["p-video"]["credits_per_unit"]["720p"] == 0.19


def test_takes_stay_at_480p_for_a_model_that_has_it():
    assert get_model("seedance-2.5").take_resolution == "480p"
    assert get_model("seedance-2.0").take_resolution == "480p"


def test_editor_sees_models_with_credits_but_no_dollars(editor):
    models = editor.get("/models").json()
    assert [m["id"] for m in models if m["kind"] == "video"] == [
        "seedance-2.5",
        "seedance-2.0",
        "p-video",
        "seedance-1-lite",
        "gemini-omni-1.2",
    ]
    assert editor.get("/models/seedance-2.5").json()["credits_per_unit"]["480p"] == 1
    assert [m["id"] for m in editor.get("/models", params={"kind": "image"}).json()] == [
        "nano-banana-2.1",
        "nano-banana-pro",
    ]
    assert "price" not in editor.get("/models").text
    assert_no_dollars(editor, ["/models", "/models/seedance-2.5"])


def test_prices_are_owner_only(owner, editor):
    assert editor.get("/models/prices").status_code == 403
    prices = {p["id"]: p for p in owner.get("/models/prices").json()}
    assert prices["seedance-2.5"]["price_per_unit_usd"]["480p"] == "0.1028"


def test_unknown_model_is_404(editor):
    assert editor.get("/models/nope").status_code == 404


def test_seeded_rates_come_from_the_catalogue(editor):
    rates = {r["kind"]: r["credits_per_unit"] for r in editor.get("/credits/rates").json()}
    nb = get_model("nano-banana-2.1")
    assert rates["image-nano-banana-2.1"] == float(nb.credits_per_unit("1K"))
    assert rates["video-720p"] == float(get_model("seedance-2.5").credits_per_unit("720p"))


def test_seedance_reference_advice(editor):
    seedance = {m["id"]: m for m in editor.get("/models").json()}["seedance-2.5"]
    assert seedance["recommended_reference_images"] == 8
