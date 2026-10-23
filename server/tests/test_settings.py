import pytest

from app.settings import Settings, check_production

GOOD_DB = "postgresql+psycopg://brand:3f9a1c7e5b2d4086@db:5432/brand"


def prod(**values) -> Settings:
    return Settings(**{"env": "production", "database_url": GOOD_DB, **values})


@pytest.mark.parametrize(
    "settings",
    [
        prod(setup_token="change-me"),
        prod(setup_token="too-short-123"),
        prod(database_url="postgresql+psycopg://brand:change-me@db:5432/brand"),
    ],
)
def test_production_refuses_example_secrets(settings):
    with pytest.raises(RuntimeError, match="Fix deploy/.env"):
        check_production(settings)


def test_production_starts_with_real_secrets_or_no_setup_token():
    check_production(prod(setup_token="a" * 32))
    check_production(prod(setup_token=""))  # empty = setup switched off
    check_production(Settings(env="dev", setup_token="change-me"))  # dev is not checked
