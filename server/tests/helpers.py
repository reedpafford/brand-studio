"""Shared checks every resource PR should use:
- `assert_hidden`: another workspace gets 404 on each call.
- `assert_no_dollars`: an editor's responses contain no `*_usd` field anywhere.
"""

MP3 = b"ID3" + b"0" * 32
MP4 = b"\0\0\0\x18ftypmp42" + b"0" * 32


def assert_hidden(client, calls: list[tuple]) -> None:
    """`calls` are (method, path) or (method, path, json). Each must answer 404."""
    for method, path, *body in calls:
        r = client.request(method, path, json=body[0] if body else None)
        assert r.status_code == 404, f"{method} {path} gave {r.status_code}, expected 404"


def _usd_keys(value, where="") -> list[str]:
    if isinstance(value, dict):
        found = [f"{where}.{k}" for k in value if k.endswith("_usd")]
        return found + [x for k, v in value.items() for x in _usd_keys(v, f"{where}.{k}")]
    if isinstance(value, list):
        return [x for i, v in enumerate(value) for x in _usd_keys(v, f"{where}[{i}]")]
    return []


def assert_no_dollars(client, paths: list[str]) -> None:
    """GET each path (as an editor) and fail if any `*_usd` field appears."""
    for path in paths:
        r = client.get(path)
        assert r.status_code == 200, f"GET {path} gave {r.status_code}"
        assert not _usd_keys(r.json()), f"GET {path} sent dollars: {_usd_keys(r.json())}"
