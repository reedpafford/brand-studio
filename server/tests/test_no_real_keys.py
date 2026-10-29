"""No test can make a paid call. conftest empties every key and refuses any connection off this
machine (and to the sandbox's proxy); and a paid provider with no key sends nothing at all,
since a bare request could be signed on the way by a network proxy."""

import pytest

from app.providers import NoKey
from app.providers.claude import ClaudeProvider
from app.providers.kie import KieSuno
from app.providers.replicate import ReplicateProvider
from app.settings import Settings
from tests.conftest import OffMachine

NEVER = "https://api.replicate.com/v1"


def test_no_key_reaches_a_test():
    settings = Settings()
    assert settings.anthropic_key.get_secret_value() == ""
    assert settings.replicate_token.get_secret_value() == ""
    assert settings.kie_api_key.get_secret_value() == ""


class Untouchable:
    """A client that fails the test if anything is sent through it."""

    def request(self, *args, **kwargs):
        raise AssertionError("A provider with no key sent a request.")


def test_a_paid_provider_with_no_key_sends_nothing():
    image = {"model": "nano-banana-2.1", "input": {"prompt": "x"}}
    with pytest.raises(NoKey):
        ReplicateProvider(NEVER, Untouchable()).submit("image", image)
    with pytest.raises(NoKey):
        KieSuno("https://api.kie.ai/api/v1", "", (), client=Untouchable()).poll("task")
    with pytest.raises(NoKey):
        ClaudeProvider("", client=Untouchable())._ask({"step": "x", "system": []}, "x")


def test_a_real_provider_cannot_reach_the_network_from_a_test(monkeypatch):
    # Even if the guard ever fails, this request can't cost anything: Replicate refuses an
    # unknown model version before running it.
    from app.providers import replicate as module

    model = module._model({"model": "nano-banana-2.1"})
    unknown = model.model_copy(update={"provider_version": "0" * 64})
    monkeypatch.setattr(module, "_model", lambda _input: unknown)
    replicate = ReplicateProvider(NEVER, token="not-a-real-token")  # a real client
    with pytest.raises(Exception) as caught:
        replicate.submit("image", {"model": "nano-banana-2.1", "input": {"prompt": "x"}})
    chain, exc = [], caught.value
    while exc is not None:
        chain.append(exc)
        exc = exc.__cause__ or exc.__context__
    assert any(isinstance(e, OffMachine) or "never reach the network" in str(e) for e in chain)
