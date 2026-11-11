"""The planning model as a setting (`Settings.one_pass_model`, BS_ONE_PASS_MODEL): only the
one-pass director's plan call is asked on it, and that call's cost and its estimate are the
chosen model's. Empty: the model every step uses. No paid call: a mocked Anthropic."""

import json
from decimal import Decimal

import httpx2 as httpx
import pytest
from anthropic import DefaultHttpxClient

from app import claude, one_pass, prompts
from app.providers.claude import ClaudeProvider, model_for
from app.providers.fake_local import FakeWriter
from app.settings import Settings, get_settings
from tests.helpers import claude_stream
from tests.test_one_pass import BODY, SCRIPT, _jobs, _run

SONNET = "claude-sonnet-5-5"
ASKED = (f"<video_model>X: 4–15 s per clip</video_model>\n<cast>\n</cast>\n"
         f"<script>\n{prompts.number_lines(SCRIPT)}\n</script>")  # fmt: skip


def _provider(seen: list) -> ClaudeProvider:
    """Claude answering each step with its stand-in's answer, and what it was asked."""
    answers = {"one_pass": FakeWriter()._one_pass(ASKED),
               "treatment": prompts.stand_in_treatment(SCRIPT)}  # fmt: skip

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        step = "one_pass" if "shooting plan" in body["system"][0]["text"] else "treatment"
        return httpx.Response(200, content=claude_stream(json.dumps(answers[step])),
                              headers={"content-type": "text/event-stream"})  # fmt: skip

    client = claude.make_client("k", DefaultHttpxClient(transport=httpx.MockTransport(handler)))
    return ClaudeProvider("k", client)


def _ask(provider, step: str):
    system = ["The shooting plan." if step == "one_pass" else "The story."]
    return provider.run("write-claude", {"step": step, "system": system, "prompt": ASKED})


def test_only_the_plan_call_is_asked_on_the_model_set_and_its_cost_is_that_models(monkeypatch):
    seen: list = []
    provider = _provider(seen)
    usual = _ask(provider, "one_pass")
    assert seen[-1]["model"] == claude.MODEL == model_for("one_pass")  # empty: nothing changes
    assert usual.usage[0].cost_usd == Decimal("0.0144")  # 1,000 in, 500 out, 2,000 cache reads
    monkeypatch.setattr(get_settings(), "one_pass_model", SONNET)
    plan = _ask(provider, "one_pass")
    assert plan.state == "succeeded" and seen[-1]["model"] == SONNET
    assert plan.usage[0].cost_usd == Decimal("0.0072")  # the same tokens at Sonnet 5.5's price
    story = _ask(provider, "treatment")
    assert seen[-1]["model"] == claude.MODEL and model_for("director") == claude.MODEL
    assert story.usage[0].cost_usd == Decimal("0.0144")  # every other step: as it was


def test_the_plans_estimate_follows_the_model(app, owner, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "one_pass", True)
    monkeypatch.setattr(get_settings(), "one_pass_model", SONNET)
    assert one_pass.plan_units() == Decimal("0.5") == claude.price_ratio(SONNET)
    owner.post("/freestyles", json={**BODY, "mode": "ask"})
    _run(app, db, ticks=4, start=False)
    (plan,) = _jobs(db, "one_pass")
    assert plan.credits == Decimal("1.5")  # half a usual writing call's 3 credits
    monkeypatch.setattr(get_settings(), "one_pass_model", "")
    assert one_pass.plan_units() == 1


def test_a_model_the_site_cannot_price_is_refused_at_start_up():
    assert Settings(one_pass_model="claude-opus-5-5").one_pass_model == "claude-opus-5-5"
    with pytest.raises(ValueError) as no:
        Settings(one_pass_model="claude-haiku-5-5")
    assert (
        "BS_ONE_PASS_MODEL is “claude-haiku-5-5”, which isn't a model this site can price. "
        "Set it to claude-sonnet-5-5 or claude-opus-5-5, or leave it empty"
    ) in str(no.value)
