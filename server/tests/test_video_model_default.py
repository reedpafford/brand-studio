"""Each style picks its default video model (Reed, 3 Nov: "Seedance 2.5 is what we use for pixar
(song and house) videos. Omni is for human skits/movies."; "seedance 2.0 provides good b-roll
footage"; 6 Nov: "keep seedance for the animated and expression-full ones for now. Omni is more
for the realistic stuff").
The order: a video's own pick, then Seedance 2.5 for a song (lip-sync), then the
style's `video_model:`, then the catalogue's."""

from app import guides
from app.breakdown import video_model
from app.catalogue import catalogue
from app.credits import plan_cost
from app.models.projects import Project

SEEDANCE, B_ROLL, REAL = "seedance-2.5", "seedance-2.0", "gemini-omni-1.2"


def test_every_style_and_lane_names_a_model_in_the_catalogue():
    for s in guides.styles():
        assert s["video_model"] in catalogue(), s["id"]


def test_pixar_and_house_default_to_seedance_2_5():
    for look in ("disney-pixar", "house"):
        for kind in ("story", "narrated", None):
            assert video_model(look=look, kind=kind).id == SEEDANCE, (look, kind)


def test_the_other_animated_styles_default_to_seedance_2_0_and_ugc_to_omni():
    for kind in ("story", "narrated"):
        for look in ("claymation", "claymation-goofy", "skeleton-cute", "zack-d", "dr-pickle"):
            assert video_model(look=look, kind=kind).id == B_ROLL, (look, kind)
        assert video_model(look="ugc", kind=kind).id == REAL, kind


def test_a_song_keeps_seedance_2_5_for_its_lip_sync_in_any_style():
    for look in ("house", "claymation", "disney-pixar"):
        assert video_model(look=look, kind="song").id == SEEDANCE, look


def test_a_models_chosen_for_the_video_always_wins():
    video = Project(look="disney-pixar", video_model="p-video")
    assert video_model(video, kind="song").id == "p-video"
    assert video_model(Project(look="claymation", video_model=None), kind="narrated").id == B_ROLL


def test_quotes_use_the_resolved_model(db):
    def cost(**kw):
        return plan_cost(db, 1, 60, None, 0, **kw)

    assert cost(look="claymation", kind="story") < cost(look="house", kind="story")
    assert cost(look="house", kind="story") == cost(look="disney-pixar", kind="story")
    chosen = cost(video=Project(look="house", video_model="p-video"), kind="story")
    assert chosen not in (cost(look="house", kind="story"), cost(look="claymation", kind="story"))
