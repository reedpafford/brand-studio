"""The v6 library (S8, S-gaps-05): an item's archive date, who made it, a character's presenter
"how it appears" and usual place; and a brand screen of a product links to the library product
(`product_id`) instead of naming it (`product`), so a product is one record with its pictures.
Each brand's product names are matched to its products by name (any case); a name with no
product makes one, named as the screens named it.

Revision ID: n31
Revises: n30
"""

import sqlalchemy as sa
from alembic import op

revision = "n31"
down_revision = "n30"
branch_labels = None
depends_on = None


SCREENS = """SELECT s.id, s.brand_id, s.product, b.workspace_id FROM brand_screens s
JOIN brands b ON b.id = s.brand_id WHERE s.product != ''"""
MATCH = """SELECT i.id FROM library_items i JOIN library_item_brands ib ON ib.item_id = i.id
WHERE ib.brand_id = :b AND i.kind = 'prop' AND NOT i.archived AND i.owner_project_id IS NULL
AND i.owner_script_id IS NULL AND lower(trim(i.name)) = :n ORDER BY i.id"""
MAKE = """INSERT INTO library_items (workspace_id, kind, name, notes, short_description,
main_claim, image_file_ids, outfits, sheet_approved, look_sheets, sheet_look, version, archived,
created_at) VALUES (:w, 'prop', :n, '', '', '', '[]', '[]', :f, '{}', 'house', 1, :f,
CURRENT_TIMESTAMP)"""
NEWEST = "SELECT max(id) FROM library_items WHERE workspace_id = :w"
LINK = "INSERT INTO library_item_brands (item_id, brand_id) VALUES (:i, :b)"
PICTURE = "UPDATE brand_screens SET product_id = :p WHERE id = :s"
BACK = """UPDATE brand_screens SET product = (SELECT substr(name, 1, 60) FROM library_items
WHERE library_items.id = brand_screens.product_id) WHERE product_id IS NOT NULL"""


def upgrade() -> None:
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("created_by_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("presenter", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("place_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_library_items_created_by_id", "users",
                                    ["created_by_id"], ["id"])  # fmt: skip
        batch_op.create_foreign_key("fk_library_items_place_id", "library_items",
                                    ["place_id"], ["id"])  # fmt: skip
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("product_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_brand_screens_product_id", "library_items",
                                    ["product_id"], ["id"])  # fmt: skip
        batch_op.create_index("ix_brand_screens_product_id", ["product_id"])
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE library_items SET archived_at = created_at WHERE archived"))
    made: dict[tuple[int, str], int] = {}
    for screen_id, brand_id, product, workspace_id in conn.execute(sa.text(SCREENS)).all():
        key = (brand_id, " ".join(product.split()).lower())
        if key not in made:
            found = conn.execute(sa.text(MATCH), {"b": brand_id, "n": key[1]}).first()
            if found is None:
                name = " ".join(product.split())[:120]
                conn.execute(sa.text(MAKE), {"w": workspace_id, "n": name, "f": False})
                found = conn.execute(sa.text(NEWEST), {"w": workspace_id}).first()
                conn.execute(sa.text(LINK), {"i": found[0], "b": brand_id})
            made[key] = found[0]
        conn.execute(sa.text(PICTURE), {"p": made[key], "s": screen_id})
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.drop_column("product")


def downgrade() -> None:
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("product", sa.String(length=60), nullable=False,
                                      server_default=""))  # fmt: skip
    op.get_bind().execute(sa.text(BACK))
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.drop_index("ix_brand_screens_product_id")
        batch_op.drop_constraint("fk_brand_screens_product_id", type_="foreignkey")
        batch_op.drop_column("product_id")
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.drop_constraint("fk_library_items_place_id", type_="foreignkey")
        batch_op.drop_constraint("fk_library_items_created_by_id", type_="foreignkey")
        batch_op.drop_column("place_id")
        batch_op.drop_column("presenter")
        batch_op.drop_column("created_by_id")
        batch_op.drop_column("archived_at")
