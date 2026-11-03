"""Dr. Pickle (app/guides/styles/dr-pickle), a new style from Reed's six reference videos, 3 Nov:
a blunt cartoon doctor over full-frame B-roll of anatomy bodies."""

from app import guides, prompts
from app.prompts import check


def test_dr_pickle_loads_off_with_a_sample_and_all_five_looks():
    look = prompts.style("dr-pickle")
    assert look["name"] == "Dr. Pickle" and look["kind"] == "look"
    assert look["on"] is False  # Reed switches it on
    assert all(look["sections"][t] for t in guides.TOKENS)
    assert "dr-pickle" in [s["id"] for s in prompts.styles()]
    assert guides.sample("dr-pickle").startswith("The cartoon doctor")


def test_dr_pickle_briefs_the_writers_with_measured_pacing_and_reeds_note():
    pacing = guides.style("dr-pickle")["sections"]["pacing"]
    assert "range to be set" not in pacing and "of 6" in pacing
    for k in ("must keep", "safe to vary", "combines with", "The host"):
        assert k in guides.style("dr-pickle")["sections"], k
    breakdown = prompts.system("breakdown", "dr-pickle")
    assert "### pacing\n" in breakdown and "never cut" in breakdown
    assert "cusses a lot - this is very important" in prompts.system("script_draft", "dr-pickle")
    assert "pixar" not in "\n".join(guides.style("dr-pickle")["sections"].values()).lower()


def test_dr_pickle_examples_are_notes_never_fed_to_the_steps():
    """Its studies are evidence (examples/*/notes.md), not study.md: no example reaches a prompt."""
    names = {n for n, _ in guides.studies("narrated", "dr-pickle")}
    assert not names & {"anatomy-ladder", "goo-gut", "glass-skeleton-feet"}
    folder = guides.ROOT / "styles" / "dr-pickle" / "examples"
    assert len(list(folder.glob("*/notes.md"))) == 6 and not list(folder.glob("*/study.md"))


def test_dr_pickle_repairs_gore_words():
    assert ("gore", "glow") in prompts.look_banned("dr-pickle")
    assert check.look_words("A flayed body, blood and gore.", "dr-pickle")[0] == (
        "A muscle-anatomy body, glow and glow."
    )
