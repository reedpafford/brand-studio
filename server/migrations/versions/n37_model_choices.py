"""The model each clip is made with, who changed a video's settings, and how its presenter
appears (v6 F, S-gaps-05 V1, Reed's L3).

`project_clips.model` (JSON, nullable): the clip's own model, {id, why, by}, when the director
chose one for it (a talker's shot on Omni, a B-roll shot on Seedance 1 Lite); null: the
video's model. `projects.settings_log` (JSON list, default []): each settings switch, newest
last, {field, was, now, by: "person" | "director", by_id, why, at}, so a person's own choice
wins over the director's and the director's switch has an Undo. `projects.presenter`
(String(20), nullable): how a Presenter video's presenter appears, "talks" (to camera, HeyGen,
B-roll cut in), "corner" (HeyGen, keyed over the B-roll) or "acts" (in the story, Omni); null:
the style's own starting choice. `projects.omni_voice` (String(300), nullable): how the
talker's voice is described to Omni, the same words in every clip where they speak on it.
`projects.narration_only` (Boolean, nullable): a person asked for narration only, so no talker
speaks on Omni. `projects.voice` (String(60), nullable): the narrator a person chose for this
video, "stock:<app voice>" or "voice:<id>"; null: its own. `host_pieces.how` (String(20),
nullable): the way the presenter appears that a host take was made for, so a switch makes a
fresh one; the hosts made before n37 are filled in (a UGC talker talks, the rest a corner).

Revision ID: n37
Revises: n36
"""

import sqlalchemy as sa
from alembic import op

revision = "n37"
down_revision = "n36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("model", sa.JSON(), nullable=True))
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("settings_log", sa.JSON(), nullable=False,
                                      server_default="[]"))  # fmt: skip
        batch_op.add_column(sa.Column("presenter", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("omni_voice", sa.String(300), nullable=True))
        batch_op.add_column(sa.Column("narration_only", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("voice", sa.String(60), nullable=True))
    with op.batch_alter_table("host_pieces", schema=None) as batch_op:
        batch_op.add_column(sa.Column("how", sa.String(20), nullable=True))
    op.execute(  # every host made so far: a UGC talker talks, the rest sat in a corner
        "UPDATE host_pieces SET how = (SELECT CASE WHEN projects.look = 'ugc' THEN 'talks' "
        "ELSE 'corner' END FROM projects WHERE projects.id = host_pieces.project_id)"
    )


def downgrade() -> None:
    with op.batch_alter_table("host_pieces", schema=None) as batch_op:
        batch_op.drop_column("how")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("voice")
        batch_op.drop_column("narration_only")
        batch_op.drop_column("omni_voice")
        batch_op.drop_column("presenter")
        batch_op.drop_column("settings_log")
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_column("model")
