"""New video's picks on a video (v6): `projects.attachments`, the pictures or clips attached
for that video only (rule 12; S-gaps-01, option 3), a JSON list of file ids, default empty;
and `projects.reel_script_id`, the reel it was adapted from (Use a reel, S2-07).

Revision ID: n32
Revises: n31
"""

import sqlalchemy as sa
from alembic import op

revision = "n32"
down_revision = "n31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("attachments", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(sa.Column("reel_script_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_projects_reel_script_id", "scripts", ["reel_script_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint("fk_projects_reel_script_id", type_="foreignkey")
        batch_op.drop_column("reel_script_id")
        batch_op.drop_column("attachments")
