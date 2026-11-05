"""A short Brand kit (S-gaps-05 L1, Reed 4 Nov): a brand keeps its name, logo, colours, and tone
and rules. The rest goes, the script and the director carrying it: end line and CTA lines (rule
18: the ending comes from the script), never say and do lists, legal line, audience, fonts, style
board, end card, music style, the default style, language and cast. Videos' end-line lock goes
with it. Import from website is dropped (L2): its reads were jobs, so nothing else is stored.
Downgrade adds the columns back empty.

Revision ID: n36
Revises: n35
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "n36"
down_revision = "n35"
branch_labels = None
depends_on = None

TEXT = ("end_line", "legal_line", "audience", "music_style")
LISTS = ("never_say", "fonts", "do_list", "dont_list", "cta_lines", "default_cast")
FILES = ("style_board_file_id", "end_card_file_id")


def upgrade() -> None:
    conn = op.get_bind()
    # A JSON bind: a plain string is sent as VARCHAR, which Postgres won't put in a JSON column
    update = sa.text("UPDATE projects SET locks = :l WHERE id = :i").bindparams(
        sa.bindparam("l", type_=sa.JSON())
    )
    for pid, locks in conn.execute(sa.text("SELECT id, locks FROM projects")).all():
        found = json.loads(locks) if isinstance(locks, str) else (locks or {})
        if "end_line" in found:
            found.pop("end_line")
            conn.execute(update, {"l": found, "i": pid})
    with op.batch_alter_table("brands", schema=None) as batch_op:
        for name in FILES:
            batch_op.drop_constraint(f"fk_brands_{name}_files", type_="foreignkey")
        for name in (*TEXT, *LISTS, *FILES, "default_language", "default_look"):
            batch_op.drop_column(name)


def downgrade() -> None:
    with op.batch_alter_table("brands", schema=None) as batch_op:
        for name in TEXT:
            batch_op.add_column(sa.Column(name, sa.Text(), nullable=False, server_default=""))
        for name in LISTS:
            batch_op.add_column(sa.Column(name, sa.JSON(), nullable=False,
                                          server_default="[]"))  # fmt: skip
        for name in FILES:
            batch_op.add_column(sa.Column(name, sa.Integer(), nullable=True))
            batch_op.create_foreign_key(f"fk_brands_{name}_files", "files", [name], ["id"])
        batch_op.add_column(sa.Column("default_language", sa.String(length=10), nullable=False,
                                      server_default="en"))  # fmt: skip
        batch_op.add_column(sa.Column("default_look", sa.String(length=40), nullable=False,
                                      server_default="house"))  # fmt: skip
