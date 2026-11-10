"""Footage folders (Reed, 10 Nov): the Footage tab's own tree of the folders' mechanism, nested
as in his Drive; an upload names its folder path (made where missing) and may skip the paid AI
description, or ask for it with the folder and file name as hints, its real cost read per clip
and in total; the director reads each clip's folder. Stand-ins only."""

from decimal import Decimal

from app import folders, footage
from app.enhance import project_context
from app.models.files import MediaUpload
from app.models.jobs import Job, Usage
from tests.conftest import file_into, first_brand, run_writer
from tests.helpers import product
from tests.test_footage import _add
from tests.test_omni_talker import _video


def _tree(client, brand):
    return {f["name"]: f for f in client.get(f"/brands/{brand}/folders?footage=true").json()}


def test_an_upload_makes_its_folder_path_names_its_product_and_may_skip_the_ai(db, owner):
    brand = first_brand(owner)
    one = _add(owner, brand, folder=" Product shots / Close-ups ", ai_describe="false").json()
    two = _add(owner, brand, folder="product shots/Close-ups", description="The lid.").json()
    tree = _tree(owner, brand)
    assert set(tree) == {"Product shots", "Close-ups"}  # matched by name, any case
    assert tree["Close-ups"]["parent_id"] == tree["Product shots"]["id"]
    assert (one["folder"], one["folder_id"]) == ("Product shots/Close-ups", tree["Close-ups"]["id"])
    assert two["folder_id"] == one["folder_id"] and tree["Close-ups"]["items"]["footage"] == 2
    assert not one["describing"] and one["description"] == ""
    assert not db.query(Job).filter(Job.kind == footage.KIND).count()  # no paid call
    guard = product(db, brand, "PalaceGuard")
    db.commit()
    named = _add(owner, brand, folder="PalaceGuard", product="palaceguard", ai_describe="false")
    assert named.json()["product_id"] == guard  # by its name, as the Drive folder says
    assert _add(owner, brand, product="Nope").status_code == 422
    assert _add(owner, brand, ai_describe="false").json()["folder"] == ""  # no path: the top
    assert owner.get(f"/brands/{brand}/folders").json() == []  # never in the videos' tree


def test_footage_folders_nest_move_rename_and_delete_with_undo(owner, editor):
    brand = first_brand(owner)
    clip = _add(owner, brand, folder="Product shots/Close-ups", description="Lid.").json()
    tree = _tree(owner, brand)
    shots, close = tree["Product shots"]["id"], tree["Close-ups"]["id"]
    video = owner.post(f"/brands/{brand}/folders", json={"name": "Ads"}).json()["id"]
    no = file_into(owner, "footage", clip["id"], video)
    assert (no.status_code, no.json()["detail"]) == (409, folders.OTHER_TREE)
    moved = file_into(editor, "footage", clip["id"], shots).json()  # anyone files footage
    assert moved["was"] == [{"id": clip["id"], "folder_id": close}]  # Undo files it back
    file_into(owner, "footage", clip["id"], close)  # Undo
    owner.patch(f"/folders/{close}", json={"name": "Macro"})
    assert owner.get(f"/brands/{brand}/footage").json()[0]["folder"] == "Product shots/Macro"
    assert owner.delete(f"/folders/{close}").json()["moved"] == 1
    (up,) = owner.get(f"/brands/{brand}/footage").json()
    assert (up["folder_id"], up["folder"]) == (shots, "Product shots")  # up a level
    owner.delete(f"/folders/{shots}")  # the whole tree: to the top
    assert owner.get(f"/brands/{brand}/footage").json()[0]["folder_id"] is None
    owner.post(f"/folders/{shots}/restore")  # each Undo brings back what it deleted
    assert owner.get(f"/brands/{brand}/footage").json()[0]["folder"] == "Product shots"
    owner.post(f"/folders/{close}/restore")
    assert owner.get(f"/brands/{brand}/footage").json()[0]["folder"] == "Product shots/Macro"


def test_the_director_reads_each_clips_folder(db, owner):
    video = _video(db, owner)
    _add(owner, video.brand_id, folder="Product shots/Close-ups", description="The lid opens.")
    told = project_context(db, video, "director")[0][-1]
    assert "| in Product shots/Close-ups | The lid opens." in told


def test_the_ai_reads_the_folder_and_file_name_and_its_cost_is_totalled(app, db, owner, editor):
    brand = first_brand(owner)
    clip = _add(owner, brand, folder="Product shots/Close-ups").json()  # left blank: the AI
    job = db.get(Job, db.get(MediaUpload, clip["id"]).describe_job_id)
    assert "<folder>Product shots/Close-ups</folder>\n<file>demo.mp4</file>" in job.input["prompt"]
    run_writer(app, db)
    for usd in ("0.004", "0.0012"):  # the stand-in is free: what Claude would report
        db.add(Usage(workspace_id=job.workspace_id, job_id=job.id, provider="claude",
                     kind=job.kind, units=1, unit="token", cost_usd=Decimal(usd)))  # fmt: skip
    db.commit()
    _add(owner, brand, description="Typed.")  # never in the spend
    spend = owner.get(f"/brands/{brand}/footage/spend").json()
    assert spend == {"usd": 0.0052, "clips": [{"id": clip["id"], "usd": 0.0052,
                                                "estimated": False}]}  # fmt: skip
    later = owner.get(f"/brands/{brand}/footage/spend?since=2999-01-01T00:00:00Z").json()
    assert later == {"usd": 0, "clips": []}
    assert editor.get(f"/brands/{brand}/footage/spend").status_code == 403  # dollars: owner only
