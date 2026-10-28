"""Length is optional: without a set length the newest breakdown decides the budget."""

from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import setup  # noqa: F401 - fixture


def test_the_breakdown_sets_the_budget_when_no_length_is_set(editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}"
    thirty = editor.get(url).json()["budget_credits"]
    assert thirty > 60  # 30 s set: twice its seconds and every step before them (rule 3)
    cleared = editor.patch(url, json={"planned_seconds": None}).json()
    assert cleared["planned_seconds"] is None and 30 < cleared["budget_credits"] < thirty
    editor.put(f"{url}/breakdown", json=BREAKDOWN)  # one 5 s clip
    project = editor.get(url).json()
    assert project["breakdown_seconds"] == 5 and 10 < project["budget_credits"] < thirty
    editor.patch(url, json={"planned_seconds": 40})
    assert editor.get(url).json()["budget_credits"] > max(80, thirty)  # a set length wins


def test_a_project_can_start_without_a_length(editor):
    fomo = editor.get("/brands").json()[0]["id"]
    made = editor.post("/projects", json={"brand_id": fomo, "name": "Long ad"})
    assert made.status_code == 201, made.text
    assert made.json()["planned_seconds"] is None and made.json()["budget_credits"] > 30
