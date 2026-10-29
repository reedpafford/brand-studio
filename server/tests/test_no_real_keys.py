"""No test can make a paid call: conftest empties every key and refuses any connection off
this machine (a keyless Replicate request would otherwise go out bare for a proxy to sign)."""

import pytest

from app.providers.replicate import ReplicateProvider
from app.settings import Settings
from tests.conftest import OffMachine


def test_no_key_reaches_a_test():
    settings = Settings()
    assert settings.anthropic_key.get_secret_value() == ""
    assert settings.replicate_token.get_secret_value() == ""
    assert settings.kie_api_key.get_secret_value() == ""


def test_a_real_provider_cannot_send_from_a_test(monkeypatch):
    # Even if the guard ever fails, this request can't cost anything: Replicate refuses an
    # unknown model version before running it.
    from app.providers import replicate as module

    model = module._model({"model": "nano-banana-2.1"})
    monkeypatch.setattr(
        module, "_model", lambda _input: model.model_copy(update={"provider_version": "0" * 64})
    )
    replicate = ReplicateProvider("https://api.replicate.com/v1")  # no key, real client
    with pytest.raises(Exception) as caught:
        replicate.submit("image", {"model": "nano-banana-2.1", "input": {"prompt": "x"}})
    chain, exc = [], caught.value
    while exc is not None:
        chain.append(exc)
        exc = exc.__cause__ or exc.__context__
    assert any(isinstance(e, OffMachine) or "never reach the network" in str(e) for e in chain)
