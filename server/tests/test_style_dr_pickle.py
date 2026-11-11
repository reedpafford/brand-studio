"""Dr. Pickle (app/guides/styles/dr-pickle), a new style from Reed's reference videos, 3 Nov:
a blunt cartoon doctor over full-frame B-roll of our skeleton, a style in the Presenter format."""

from app import guides, prompts
from app.prompts import check


def test_dr_pickle_loads_on_with_its_own_sample_and_all_five_looks():
    look = prompts.style("dr-pickle")
    assert look["name"] == "Dr. Pickle" and look["kind"] == "look"
    assert look["on"] is True and look["own_sample"] is True  # on (Reed, 10 Nov: every style); D3
    assert all(look["sections"][t] for t in guides.TOKENS)
    assert "dr-pickle" in [s["id"] for s in prompts.styles()]
    assert guides.sample("dr-pickle").startswith("The cartoon doctor")


def test_dr_pickle_briefs_the_writers_with_reeds_answers_and_measured_pacing():
    sections = guides.style("dr-pickle")["sections"]
    assert "range to be set" not in sections["pacing"] and "of 5" in sections["pacing"]
    for k in ("must keep", "safe to vary", "combines with", "The host", "camera"):
        assert k in sections, k
    assert "It is always a doctor. The name is just a name." in sections["The host"]  # D1
    assert "smooth ivory-cream bones" in sections["sheet_look"]  # D6: our Skeleton figure
    breakdown = prompts.system("breakdown", "dr-pickle")
    assert "### pacing\n" in breakdown and "never cut" in breakdown
    script = prompts.system("script_draft", "dr-pickle")
    assert "cusses a lot - this is very important" in script and "no bleep by default" in script
    text = "\n".join(sections.values()).lower()
    assert "caption" not in text and "pixar" not in text  # captions come in post (Reed, 3 Nov)


def test_dr_pickle_examples_are_notes_never_fed_to_the_steps():
    """Its studies are evidence (examples/*/notes.md), not study.md: no example reaches a prompt."""
    names = {n for n, _ in guides.studies("narrated", "dr-pickle")}
    assert not names & {"anatomy-ladder", "goo-gut", "glass-skeleton-feet"}
    folder = guides.ROOT / "styles" / "dr-pickle" / "examples"
    assert len(list(folder.glob("*/notes.md"))) == 5 and not list(folder.glob("*/study.md"))


def test_dr_pickle_repairs_gore_words():
    assert ("gore", "glow") in prompts.look_banned("dr-pickle")
    assert check.look_words("A flayed body, blood and gore.", "dr-pickle")[0] == (
        "A muscle-anatomy body, glow and glow."
    )
