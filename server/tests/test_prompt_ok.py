"""Read each clip prompt: Looks good (or Edit) before the takes are made (decision b)."""

from tests.test_clip_takes import clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


def test_a_prompt_is_marked_looks_good_undone_or_edited(editor, setup, clip):  # noqa: F811
    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    assert clip["prompt_ok"] is False  # new prompts are unread
    assert editor.post(f"{url}/prompt-ok").json()["prompt_ok"] is True
    assert editor.delete(f"{url}/prompt-ok").json()["prompt_ok"] is False
    body = {"prompt": clip["prompt"] + " Slow push in.", "references": clip["references"]}
    assert editor.put(url, json=body).json()["prompt_ok"] is True  # an edit means it was read
