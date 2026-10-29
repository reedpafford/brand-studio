"""Model providers behind one interface: Replicate for real work, a fake for tests."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Protocol


class NetworkError(Exception):
    """The provider couldn't be reached. The only kind of error that is retried."""


class NoKey(RuntimeError):
    """A paid provider with no key refuses to send: a request without one could still be
    signed on the way (a sandbox's network proxy adds credentials), and so cost money."""

    def __init__(self, service: str):
        super().__init__(f"{service} has no key here, so nothing was sent.")


class NotStarted(Exception):
    """The provider certainly did not start the work (e.g. it said "too busy").
    Safe to try again later, even for paid work."""


@dataclass
class UsageItem:
    units: Decimal
    unit: str
    cost_usd: Decimal
    estimated: bool = False  # True when the provider didn't report the amount used


@dataclass
class Result:
    """`output` is shown to every editor, so it must never contain prices or costs:
    money goes in `usage` only. `error` is raw text and is kept owner-only."""

    state: Literal["running", "succeeded", "failed"]
    output: dict | None = None
    error: str = ""
    usage: list[UsageItem] = field(default_factory=list)
    files: list[str] = field(default_factory=list)  # provider URLs to copy into our storage


class Provider(Protocol):
    name: str
    paid: bool  # True if submitting costs money: such work is never auto-retried

    def submit(self, kind: str, input: dict) -> str:
        """Start the work and return the provider's reference for it."""

    def poll(self, ref: str) -> Result:
        """Check on work started earlier."""

    def fetch(self, url: str) -> tuple[bytes, str]:
        """Download one output file: (bytes, content type)."""


def get_providers(settings, storage=None) -> dict[str, Provider]:
    from app.providers.fake import FakeProvider
    from app.providers.local import LocalProvider

    if settings.fake_providers:
        from app.providers.fake_local import (
            FakeMedia,
            FakeSuno,
            FakeWriter,
            hear_song,
            hear_study,
            hear_voice,
            read_site,
            refuse_link,
            study_link,
            transcript,
        )

        local = LocalProvider(storage, transcribe=transcript, fetch_link=refuse_link,
                              hear_song=hear_song, hear_voice=hear_voice,
                              hear_study=hear_study, fetch_study=study_link,
                              read_site=read_site)  # fmt: skip
        return {
            "fake": FakeProvider(),
            "replicate": FakeMedia(),
            # The test site's one real service, once Reed switches it on (2026-10-29: real
            # Suno through KIE, test site only, with a test budget); all else stays free.
            "suno": _kie(settings, FakeSuno()) if kie_on(settings) else FakeSuno(),
            "claude": FakeWriter(),
            "local": local,
            # Look samples, real on Replicate once Reed switches them on (2026-10-29); on
            # without the key (only the worker holds it), a stand-in, never a failed job
            **(
                {REAL_SAMPLES: _replicate(settings) if samples_on(settings) else FakeMedia()}
                if settings.real_look_samples
                else {}
            ),  # fmt: skip
            # Language tests, written for real once Reed switches them on (2026-10-29); on
            # without the key (only the Claude worker holds it), a stand-in, never a failure
            **(
                {REAL_TESTS: _claude(settings) if tests_on(settings) else FakeWriter()}
                if settings.real_language_samples
                else {}
            ),  # fmt: skip
        }
    from app import site_fetch

    local = LocalProvider(storage, read_site=site_fetch.read_site if settings.site_read_real
                          else site_fetch.switched_off)  # fmt: skip
    providers = {"fake": FakeProvider(), "replicate": _replicate(settings),
                 "claude": _claude(settings), "local": local}  # fmt: skip
    if kie_on(settings):  # Suno through KIE: only once Reed switches it on
        providers["suno"] = _kie(settings)
    return providers


REAL_SAMPLES = "replicate-samples"  # the test site's lane for real look samples


def _replicate(settings):
    from app.providers.replicate import ReplicateProvider

    return ReplicateProvider(
        settings.replicate_base_url,
        delivery_hosts=tuple(settings.replicate_delivery_hosts),
        max_download_mb=settings.max_download_mb,
        token=settings.replicate_token.get_secret_value(),
    )


def samples_on(settings) -> bool:
    """Real look samples among the stand-ins: switched on, with a Replicate key."""
    return bool(settings.fake_providers and settings.real_look_samples
                and settings.replicate_token.get_secret_value())  # fmt: skip


REAL_TESTS = "claude-samples"  # the test site's lane for real language tests


def _claude(settings):
    from app.providers.claude import ClaudeProvider

    return ClaudeProvider(settings.anthropic_key.get_secret_value())


def tests_on(settings) -> bool:
    """Real language tests among the stand-ins: switched on, with a Claude key."""
    return bool(settings.fake_providers and settings.real_language_samples
                and settings.anthropic_key.get_secret_value())  # fmt: skip


def _kie(settings, stand_in=None):
    from app.providers.kie import KieSuno

    return KieSuno(settings.kie_base_url, settings.kie_api_key.get_secret_value(),
                   tuple(settings.kie_delivery_hosts), settings.max_download_mb,
                   stand_in=stand_in)  # fmt: skip


def kie_on(settings) -> bool:
    return bool(settings.kie_suno and settings.kie_api_key.get_secret_value())
