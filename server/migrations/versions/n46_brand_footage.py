"""Brand footage (Reed, 9 Nov): a clip added to a brand's Media can be footage on the library's
Footage tab (`media_uploads.footage`), with what it shows (`description`), its product
(`product_id`), two frames (`frame_file_ids`), its AI description's job while it's written
(`describe_job_id`) and why the AI's words aren't in, when they aren't (`describe_note`).
Every existing upload is Media only.

Revision ID: n46
Revises: n45
"""

import sqlalchemy as sa
from alembic import op

revision = "n46"
down_revision = "n45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("media_uploads", schema=None) as batch_op:
        batch_op.add_column(sa.Column("footage", sa.Boolean(), nullable=False,
                                      server_default=sa.false()))  # fmt: skip
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=False,
                                      server_default=""))  # fmt: skip
        batch_op.add_column(sa.Column("product_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("frame_file_ids", sa.JSON(), nullable=False,
                                      server_default="[]"))  # fmt: skip
        batch_op.add_column(sa.Column("describe_job_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("describe_note", sa.Text(), nullable=False,
                                      server_default=""))  # fmt: skip
        batch_op.create_foreign_key("fk_media_uploads_product_id_library_items",
                                    "library_items", ["product_id"], ["id"])  # fmt: skip
        batch_op.create_foreign_key("fk_media_uploads_describe_job_id_jobs", "jobs",
                                    ["describe_job_id"], ["id"])  # fmt: skip


def downgrade() -> None:
    with op.batch_alter_table("media_uploads", schema=None) as batch_op:
        batch_op.drop_constraint("fk_media_uploads_describe_job_id_jobs", type_="foreignkey")
        batch_op.drop_constraint("fk_media_uploads_product_id_library_items", type_="foreignkey")
        for name in ("describe_note", "describe_job_id", "frame_file_ids", "product_id",
                     "description", "footage"):  # fmt: skip
            batch_op.drop_column(name)
