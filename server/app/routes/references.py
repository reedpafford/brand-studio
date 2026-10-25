"""The reference reels a brief can adapt ("make this reel for fomo"): every folder under
docs/references with a BREAKDOWN.json (and a contact.jpg contact sheet). Picking one on the
brief (`reference_id`) copies its breakdown into the project; live-action shots are always
removed when it's used (prompts.reference_block)."""

import json
import re
from functools import cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.auth import current_user
from app.reference import checked

router = APIRouter(prefix="/references", tags=["references"], dependencies=[Depends(current_user)])
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")


class ReferenceOut(BaseModel):
    id: str  # e.g. "fomo-DehudnaAmce"
    name: str
    logline: str
    seconds: float
    style: str
    brand: str  # the brand it was picked for ("fomo"), or ""
    has_thumbnail: bool


@cache
def catalogue(root: str) -> dict[str, tuple[ReferenceOut, Path]]:
    """id -> (summary, folder), brand-picked reels first. Read once per process."""
    out = {}
    for path in sorted(Path(root).glob("**/BREAKDOWN.json")):
        folder, data = path.parent, json.loads(path.read_text())
        ref_id = folder.name
        if not SAFE_ID.fullmatch(ref_id) or ref_id in out:
            continue
        # Top-level folders are named <brand>-<id> (fomo-DehudnaAmce); collections sit deeper.
        top = folder.parent == Path(root) and "-" in ref_id
        brand = ref_id.split("-")[0] if top else ""
        logline = data.get("logline", "")
        out[ref_id] = (
            ReferenceOut(
                id=ref_id,
                name=logline.split(",")[0][:80] or ref_id,
                logline=logline,
                seconds=data.get("duration_seconds", 0),
                style=data.get("style", ""),
                brand=brand,
                has_thumbnail=(folder / "contact.jpg").exists(),
            ),
            folder,
        )
    return dict(sorted(out.items(), key=lambda kv: (not kv[1][0].brand, kv[0])))


def find(request: Request, ref_id: str) -> tuple[ReferenceOut, Path]:
    found = catalogue(request.app.state.settings.references_dir).get(ref_id)
    if not found:
        raise HTTPException(404, "No such reference reel.")
    return found


def load(request: Request, ref_id: str) -> dict:
    """The reel's breakdown as a project stores it (checked and trimmed), tagged with its id."""
    _, folder = find(request, ref_id)
    return checked({**json.loads((folder / "BREAKDOWN.json").read_text()), "source_id": ref_id})


@router.get("", response_model=list[ReferenceOut])
def list_references(request: Request):
    return [ref for ref, _ in catalogue(request.app.state.settings.references_dir).values()]


@router.get("/{ref_id}/thumbnail", response_class=FileResponse)
def thumbnail(ref_id: str, request: Request):
    ref, folder = find(request, ref_id)
    if not ref.has_thumbnail:
        raise HTTPException(404, "This reel has no contact sheet.")
    return FileResponse(folder / "contact.jpg", media_type="image/jpeg")
