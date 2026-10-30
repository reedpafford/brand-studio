"""Screen figures (n17): where a shot's figure is written on a brand screen (figure_spot, null:
never drawn on), set for fomo's three money screens as measured on their pictures in
assets/brands/fomo/screens (a new workspace gets them from screens.json when it's seeded).

Revision ID: n17
Revises: n15
"""

import sqlalchemy as sa
from alembic import op

revision = "n17"
down_revision = "n15"  # tracks next's head for CI; re-pointed to the head just before merge
branch_labels = None
depends_on = None

SPOTS = {
    "Home (rich)": {"box": [20, 128, 445, 232], "at": [28, 132], "size": 54},
    "Token chart up": {"box": [0, 96, 603, 640], "at": [24, 104], "size": 60,
                       "chart": [0, 270, 603, 620]},
    "Token chart down": {"box": [0, 110, 600, 700], "at": [18, 118], "size": 60,
                         "chart": [0, 290, 600, 690]},
}  # fmt: skip


def upgrade() -> None:
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("figure_spot", sa.JSON(), nullable=True))
    update = sa.text(
        "UPDATE brand_screens SET figure_spot = :spot WHERE name = :name "
        "AND brand_id IN (SELECT id FROM brands WHERE slug = 'fomo')"
    ).bindparams(sa.bindparam("spot", type_=sa.JSON()))
    for name, spot in SPOTS.items():
        op.get_bind().execute(update, {"spot": spot, "name": name})


def downgrade() -> None:
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.drop_column("figure_spot")
