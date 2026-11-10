"""Which of a brand's clips the director is given (app/footage_rank.py): with Reed's PG brand's
~985 clips in folders, most of no product, the few in <footage> are the ones that fit this
video (product first, then words shared with the script, folder names counting most, a soft
lean to the style), near copies left out; and `find_footage` finds any clip by words, free.
A synthetic 900-clip library in PG's folders; stand-ins only, no AI call."""

from app import director_tools, footage
from app.director import RUN, STEP
from app.models.accounts import User
from app.models.files import MediaUpload, StoredFile
from app.models.folders import Folder
from app.models.jobs import Job
from app.routes.scripts import latest
from tests.helpers import product
from tests.test_omni_talker import _video

PEOPLE = ["a woman", "a man", "two friends", "a family", "an older couple", "a teenager"]
GENERIC = ["walks down a city street", "drinks coffee in a kitchen", "drives a car at dusk",
           "jogs in a park", "types on a laptop in an office", "walks a dog on the beach",
           "shops in a supermarket", "waits at a bus stop in the rain", "cooks pasta at home",
           "lifts weights at the gym", "watches the sunset from a rooftop"]  # fmt: skip
CAMPUS = ["students walk across the campus quad", "a lecture hall fills with students",
          "a student studies at a desk in her dorm", "friends talk in a dorm room",
          "graduates throw their caps", "a professor writes on a whiteboard"]  # fmt: skip
ANIMATED = ["an animated cartoon student studies at a desk", "a cartoon house with a glowing "
            "door", "an animated city skyline at night", "a 2d animation of a phone buzzing",
            "a cartoon family waves from a car"]  # fmt: skip
CHURCH = ["a congregation sings in a church", "a pastor preaches from the pulpit",
          "sunlight through a church's stained glass window", "people pray in church pews",
          "a choir rehearses in the church hall"]  # fmt: skip
GUARD = ["the PalaceGuard sensor mounted on a front door", "the PalaceGuard camera blinks "
         "on a porch", "a phone shows a PalaceGuard alert", "installing the PalaceGuard hub "
         "on a shelf"]  # fmt: skip
FOLDERS = {"Animation": (162, ANIMATED), "Campus": (113, CAMPUS), "Church": (31, CHURCH),
           "Generic": (544, GENERIC), "PalaceGuard": (50, GUARD)}  # fmt: skip
SHOTS = ["wide", "close", "slow pan"]
NEEDLE = "a church exterior at night, its neon cross glowing over the empty car park"


def _library(db, video) -> dict[str, list[int]]:
    """900 described clips in PG's folders, varied in turn (most of Generic's alike), the
    PalaceGuard ones of its product, and one clip to find among them."""
    user, guard = video.created_by_id, product(db, video.brand_id, "PalaceGuard")
    made: dict[str, list[int]] = {}
    for name, (count, scenes) in FOLDERS.items():
        folder = Folder(workspace_id=video.workspace_id, brand_id=video.brand_id, name=name,
                        footage=True, created_by_id=user)  # fmt: skip
        db.add(folder)
        db.flush()
        for n in range(count):
            scene = scenes[n % len(scenes)]
            text = (f"{PEOPLE[n % len(PEOPLE)]}: {scene}" if name == "Generic"
                    else f"{scene}, {SHOTS[n // len(scenes) % len(SHOTS)]}")  # fmt: skip
            text = NEEDLE if name == "Church" and n == 17 else text
            of = guard if name == "PalaceGuard" else None
            clip = _clip(db, video, folder.id, text, f"{name}_{n}.mp4", of)
            made.setdefault(name, []).append(clip)
    db.commit()
    return made


def _clip(db, video, folder_id, text, filename, product_id=None) -> int:
    f = StoredFile(workspace_id=video.workspace_id, key=f"footage/{filename}", filename=filename,
                   content_type="video/mp4", size=1, sha256="0" * 64)  # fmt: skip
    db.add(f)
    db.flush()
    row = MediaUpload(workspace_id=video.workspace_id, brand_id=video.brand_id,
                      created_by_id=video.created_by_id, file_id=f.id, seconds=5.0, footage=True,
                      description=text, product_id=product_id, folder_id=folder_id)  # fmt: skip
    db.add(row)
    db.flush()
    return row.id


def _given(db, video) -> list[str]:
    """The folder of each clip in the director's <footage>, in order."""
    rows = footage.relevant(db, video)
    assert rows == footage.relevant(db, video)  # the same each time: stable through the video
    return [db.get(Folder, r.folder_id).name for r in rows]


def _says(db, video, text: str, look: str = "ugc") -> None:
    latest(db, video).text, video.goal, video.name, video.look = text, "", "Ad", look
    db.commit()


def test_a_church_script_gets_church_clips_and_a_near_copy_once(app, db, owner):
    video = _video(db, owner)
    made = _library(db, video)
    twin = next(
        r for r in map(lambda i: db.get(MediaUpload, i), made["Church"]) if "pray" in r.description
    )  # the same clip again, in Generic
    _clip(db, video, db.get(MediaUpload, made["Generic"][0]).folder_id, twin.description + ".",
          "copy.mp4")  # fmt: skip
    db.commit()
    _says(db, video, "MAYA: Every Sunday I sat in the back pew.\nMAYA: The choir would sing "
          "and I'd look at the stained glass and pray nobody saw me cry.")  # fmt: skip
    given = _given(db, video)
    assert len(given) == footage.MOST and given.count("Church") >= footage.MOST - 1
    block = footage.block(db, video, "director")
    assert block.count(f"| {twin.description}") == 1  # near copies: one of them only


def test_a_palaceguard_script_gets_the_product_clips_first(app, db, owner):
    video = _video(db, owner)
    _library(db, video)
    _says(db, video, "DAN: I used to check the front door three times a night.\nDAN: Now "
          "PalaceGuard pings my phone if anything moves on the porch.")  # fmt: skip
    given = _given(db, video)
    half = footage.MOST // 2
    assert given[:half] == ["PalaceGuard"] * half  # its product first
    assert "Church" not in given and "Animation" not in given  # nothing off the story


def test_an_animated_style_leans_to_the_animation_folder(app, db, owner):
    video = _video(db, owner)
    _library(db, video)
    words = "LEO: Finals week. The student studies at a desk until dawn."
    _says(db, video, words, look="ugc")
    real = _given(db, video)
    _says(db, video, words, look="house")
    drawn = _given(db, video)
    assert drawn.count("Animation") > real.count("Animation")
    assert (drawn[0], real[0]) == ("Animation", "Campus")


def test_the_director_finds_one_clip_among_hundreds_free_and_it_joins_footage(app, db, owner):
    video = _video(db, owner)
    made = _library(db, video)
    needle = made["Church"][17]
    _says(db, video, "MAYA: I drove past it for a year before I finally went in.")
    assert f"{footage.KEY}{needle} " not in footage.block(db, video, "breakdown")
    me, jobs = db.get(User, video.created_by_id), db.query(Job).count()
    said = director_tools.run(db, me, video, {"tool": "find_footage",
                                              "note": "church exterior night"}, None)  # fmt: skip
    assert said.splitlines()[1].startswith(f"- {footage.KEY}{needle} ")  # the best match
    assert db.query(Job).count() == jobs  # no AI call, nothing charged
    db.add(
        Job(
            workspace_id=video.workspace_id,
            kind="director",
            provider="claude",
            project_id=video.id,
            output={"tool": "find_footage"},
            input={"step": STEP, RUN: {"id": "r1"}, "result": said},
        )
    )  # its turn, as logged
    db.commit()
    block = footage.block(db, video, "breakdown")
    assert block.splitlines()[2].startswith(f"- {footage.KEY}{needle} ")  # first for the plan
    assert block.count(f"\n- {footage.KEY}") == footage.MOST
    nothing = director_tools.run(db, me, video, {"tool": "find_footage", "note": "zebra"}, None)
    assert nothing.startswith("Found none of the brand's 900 clips")
