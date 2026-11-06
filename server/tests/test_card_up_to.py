"""S1-04 / P-02 (the board comparison, 6 Nov): a working video's folder card says the same "up
to" as its own header (one figure everywhere), to the owner in dollars and an editor in
credits. On the stand-ins (no paid call)."""

from app.models.projects import Project
from app.providers import get_providers
from app.worker import run_once
from tests.helpers import make_it, ok_when_asked
from tests.test_director import _made


def test_a_working_videos_card_says_its_headers_up_to(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(40):  # under way: Make it pressed, a take or two going
        run_once(db, providers, app.state.storage)
        db.expire_all()
        ok_when_asked(db)
        make_it(db)
        if (
            owner.get(f"/projects/{pid}/idea").json()["status"]["kind"] == "working"
            and (owner.get(f"/projects/{pid}/director").json()["started"])
        ):
            break
    brand = db.get(Project, pid).brand_id
    for client in (owner, editor):
        head = client.get(f"/projects/{pid}/idea").json()
        assert head["status"]["kind"] == "working", head["status"]
        cards = client.get(f"/brands/{brand}/ideas", params={"folder": "all"}).json()["ideas"]
        (card,) = [c for c in cards if c["id"] == pid]
        assert card["cost"]["kind"] == "up_to"
        assert card["cost"]["credits"] == head["up_to"]["credits"]  # one figure everywhere
        assert card["cost"]["usd"] == head["up_to"]["usd"]  # dollars to the owner, else None
