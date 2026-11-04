"""Who has watched which take (v6 piece C, S3-09): a clip the director changed stays outlined
for a person until they've watched its new take."""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class TakeSeen(Entity, Base):
    __tablename__ = "take_seen"
    __table_args__ = (UniqueConstraint("take_id", "user_id"),)
    take_id: Mapped[int] = mapped_column(
        ForeignKey("clip_takes.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
