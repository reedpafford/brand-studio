"""A narrated video keeps its narration throughout (Reed, 5 Nov): no talker speaks on Omni in
it, so drops `projects.omni_voice` (the voice described to Omni) and `projects.narration_only`
(the switch that turned that speech off). A clip that spoke on Omni loses `speaks` in
`project_clips.model`; its takes go out of date by their model as any other.

Revision ID: n39
Revises: n38
"""

import sqlalchemy as sa
from alembic import op

revision = "n39"
down_revision = "n38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("narration_only")
        batch_op.drop_column("omni_voice")


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("omni_voice", sa.String(300), nullable=True))
        batch_op.add_column(sa.Column("narration_only", sa.Boolean(), nullable=True))
