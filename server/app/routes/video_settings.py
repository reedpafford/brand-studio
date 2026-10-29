"""Video settings (flows VS1): the row's choices with their prices, the confirm for a switch
("To finish: about N credits (was M)", what goes out of date), and the switch itself, with
Undo by switching back. Rules: app/video_settings.py."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import video_settings as vs
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.projects import Project
from app.routes.projects import get_project

router = APIRouter(prefix="/projects/{project_id}/settings", tags=["video settings"])
NOT_YOURS = "Only whoever made this video, or the owner, changes its settings."


class VideoModelOut(BaseModel):
    id: str
    name: str
    credits_per_second: float
    lip_sync: bool  # false: "No lip-sync" (a song video's Sung shots become B-roll)
    default: bool  # what Auto uses
    over_cap: bool  # "Over the video limit"


class ImageModelOut(BaseModel):
    id: str
    name: str
    credits_per_still: float
    default: bool
    over_cap: bool


class SettingsOut(BaseModel):
    look: str
    video_model: str | None  # null: Auto
    image_model: str | None  # null: Auto
    aspect_ratio: str
    product_variants: dict[str, str]
    language: str  # the script's, read only ("Spanish (from the script)")
    video_models: list[VideoModelOut]
    image_models: list[ImageModelOut]
    shapes: list[str]
    flavours: dict[str, list[str]]  # product -> its variants


class SettingIn(BaseModel):
    """Exactly one setting. A model's null is Auto."""

    look: str | None = None
    video_model: str | None = None
    image_model: str | None = None
    aspect_ratio: Literal["9:16", "1:1", "16:9", "4:3", "3:4", "21:9"] | None = None
    product_variants: dict[str, str] | None = None
    undo: bool | None = None  # true: Undo, putting back `was` (never refused)


class PreviewOut(BaseModel):
    to_finish_credits: float  # "To finish: about N credits"
    was_credits: float  # "(was M)"
    stills_out_of_date: int  # made now that this switch outdates
    clips_out_of_date: int
    roles_needing_look: list[str] = []  # roles this switch leaves with no look in it (ST1)
    sung_to_broll: int  # a no-lip-sync model on a song video
    over_budget: bool
    over_cap: bool
    reason: str  # why Switch is disabled ("" when it isn't)


class SwitchOut(BaseModel):
    settings: SettingsOut
    was: dict  # Undo: switch with this


def _video(db: Session, user: User, project_id: int, change: bool = False) -> Project:
    project = get_project(db, user, project_id)
    if change and not user.is_owner and project.created_by_id != user.id:
        raise HTTPException(403, NOT_YOURS)
    return project


def _one(body: SettingIn) -> dict:
    sent = body.model_dump(exclude_unset=True, exclude={"undo"})
    if len(sent) != 1:
        raise HTTPException(422, vs.ONE)
    return sent


@router.get("", response_model=SettingsOut)
def read_settings(project_id: int, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):  # fmt: skip
    return vs.settings(db, _video(db, user, project_id))


@router.post("/preview", response_model=PreviewOut)
def preview_setting(
    project_id: int,
    body: SettingIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """The confirm for one switch: nothing changes."""
    return vs.preview(db, user, _video(db, user, project_id, change=True), _one(body))


@router.post("", response_model=SwitchOut)
def switch_setting(
    project_id: int,
    body: SettingIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Switch one setting (409 with the reason over the budget or the cap). Undo: switch with
    `was` and `undo: true`, never refused; the stills and clips made before come back as
    current."""
    project = _video(db, user, project_id, change=True)
    was = vs.switch(db, user, project, _one(body), undo=bool(body.undo))
    return SwitchOut(settings=vs.settings(db, project), was=was)
