"""Each style picks its default video model (Reed, 3 Nov: "Seedance 1.0 for b-rolls, sure, and
p-video for the talking head character"). The order: a video's own pick, then the model that
makes speech for a story script, then the style's `video_model:`, then the catalogue's."""

from app import guides
from app.breakdown import video_model
from app.catalogue import catalogue
from app.credits import plan_cost
from app.models.projects import Project

SEEDANCE, LITE = "seedance-2.5", "seedance-1-lite"


def test_every_style_and_lane_names_a_model_in_the_catalogue():
    for s in guides.styles():
        assert s["video_model"] in catalogue(), s["id"]


def test_pixar_defaults_to_seedance():
    assert video_model(look="disney-pixar", kind="narrated").id == SEEDANCE


def test_the_other_styles_and_their_lanes_default_to_seedance_1_lite_for_b_roll():
    for look in ("house", "claymation", "claymation-goofy", "skeleton-cute", "ugc"):
        assert video_model(look=look, kind="narrated").id == LITE, look


def test_a_script_with_people_speaking_or_singing_keeps_the_model_that_does_sound():
    for look in ("house", "claymation", "disney-pixar"):
        for kind in ("story", "song"):
            assert video_model(look=look, kind=kind).id == SEEDANCE, (look, kind)
    assert video_model(look="house").id == LITE  # no script named: the style's


def test_a_models_chosen_for_the_video_always_wins():
    video = Project(look="disney-pixar", video_model="p-video")
    assert video_model(video, kind="story").id == "p-video"
    assert video_model(Project(look="house", video_model=None), kind="narrated").id == LITE


def test_quotes_use_the_resolved_model(db):
    def cost(**kw):
        return plan_cost(db, 1, 60, None, 0, **kw)

    assert cost(look="house", kind="narrated") < cost(look="disney-pixar", kind="narrated")
    assert cost(look="house", kind="story") == cost(look="disney-pixar", kind="story")
    chosen = cost(video=Project(look="house", video_model="p-video"), kind="narrated")
    assert chosen not in (cost(look="house", kind="narrated"),
                          cost(look="disney-pixar", kind="narrated"))  # fmt: skip
