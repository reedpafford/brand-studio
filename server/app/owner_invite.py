"""The test site's first owner joins by a one-time invite link instead of the setup code.

Run on the server: `python -m app.owner_invite <email> [name]`. The first run makes the
workspace with the launch brands (from the repo's assets, never live data) and closes /setup.
It prints the link and nothing else keeps it (only its hash is stored). Running it again
before the link is used replaces the link; once an owner has joined it refuses.
"""

import sys
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password, new_token
from app.credits import seed_rates
from app.db import utcnow
from app.models.accounts import Invite, Role, SetupDone, User, Workspace
from app.seed import seed_brands
from app.storage import Storage

WORKSPACE = "Brand Studio Next"


def invite_first_owner(
    db: Session, storage: Storage, settings, email: str, name: str = "Reed"
) -> str:
    """Returns the raw invite token. The owner is waiting (not active) until it's accepted:
    accepting an invite brings a waiting account in with its own name and password."""
    if db.scalar(select(User).where(User.role == Role.owner, User.active)):
        raise SystemExit("This site already has an owner: invite people from the Team page.")
    workspace = db.scalar(select(Workspace))
    if not workspace:
        workspace = Workspace(name=WORKSPACE)
        db.add_all([workspace, SetupDone(id=1)])  # /setup stays closed from now on
        db.commit()
        seed_rates(db, workspace.id)
        seed_brands(db, workspace.id, storage, settings.brand_assets_dir)
    owner = db.scalar(select(User).where(User.email == email))
    if owner and owner.workspace_id != workspace.id:
        raise SystemExit("That email belongs to another workspace.")
    owner = owner or User(email=email, workspace_id=workspace.id)
    owner.name, owner.role, owner.active = name, Role.owner, False
    owner.password_hash = hash_password(new_token()[0])  # nobody knows it; the invite sets it
    db.add(owner)
    db.flush()
    for old in db.scalars(
        select(Invite).where(Invite.email == email, Invite.accepted_at.is_(None))
    ):
        db.delete(old)  # only the newest link works
    raw, digest = new_token()
    db.add(
        Invite(
            workspace_id=workspace.id,
            email=email,
            role=Role.owner,
            token_hash=digest,
            invited_by_id=owner.id,
            expires_at=utcnow() + timedelta(days=settings.invite_days),
        )
    )
    db.commit()
    return raw


def main(email: str, name: str = "Reed") -> None:  # pragma: no cover - wiring only
    import os

    from app.db import make_sessionmaker
    from app.settings import get_settings
    from app.storage import LocalStorage

    settings = get_settings()
    with make_sessionmaker(settings.database_url)() as db:
        raw = invite_first_owner(db, LocalStorage(settings.storage_dir), settings, email, name)
    print(f"https://{os.environ.get('PUBLIC_ADDRESS', 'localhost')}/invite/{raw}")


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) < 2:
        sys.exit("Usage: python -m app.owner_invite <email> [name]")
    main(*sys.argv[1:3])
