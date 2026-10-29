"""Tests never hold a real key (conftest empties them), so no test can make a paid call."""

from app.settings import Settings


def test_no_key_reaches_a_test():
    settings = Settings()
    assert settings.anthropic_key.get_secret_value() == ""
    assert settings.replicate_token.get_secret_value() == ""
    assert settings.kie_api_key.get_secret_value() == ""
    assert settings.fake_providers
