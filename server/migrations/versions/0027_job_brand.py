"""job brand: the brand each job is charged to (Usage, DECISIONS #237), backfilled by the same
rule as new jobs (app/job_brand.py)

Revision ID: 0027
Revises: 0026
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("brand_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_jobs_brand_id"), ["brand_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_jobs_brand_id_brands"), "brands", ["brand_id"], ["id"]
        )
    backfill(op.get_bind())


def backfill(conn) -> None:
    """Jobs without a brand get one by the rule in app/job_brand.py."""
    project_brand = dict(conn.execute(sa.text("SELECT id, brand_id FROM projects")).all())
    script_brand = dict(conn.execute(sa.text("SELECT id, brand_id FROM scripts")).all())
    draft_script = dict(conn.execute(sa.text("SELECT id, script_id FROM script_drafts")).all())
    item_brands: dict[int, list[int]] = {}
    for item, brand in conn.execute(sa.text("SELECT item_id, brand_id FROM library_item_brands")):
        item_brands.setdefault(item, []).append(brand)
    for job_id, project_id, raw in conn.execute(
        sa.text("SELECT id, project_id, input FROM jobs WHERE brand_id IS NULL")
    ).all():
        data = (json.loads(raw) if isinstance(raw, str) else raw) or {}
        script_id = data.get("script_id") or draft_script.get(data.get("script_draft_id"))
        brands = item_brands.get(data.get("library_item_id"), [])
        brand = (
            project_brand.get(project_id)
            or data.get("brand_id")
            or script_brand.get(script_id)
            or (brands[0] if len(brands) == 1 else None)
        )
        if brand:
            conn.execute(
                sa.text("UPDATE jobs SET brand_id = :b WHERE id = :j"), {"b": brand, "j": job_id}
            )


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_jobs_brand_id_brands"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_jobs_brand_id"))
        batch_op.drop_column("brand_id")
