from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    offers = op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(), nullable=False),
    )
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        *(sa.Column(field, sa.String(), nullable=False)
          for field in ("name", "geo", "domain", "group", "source")),
    )
    op.create_table(
        "campaign_offers",
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id"), primary_key=True),
        sa.Column("offer_id", sa.Integer(), sa.ForeignKey("offers.id"), primary_key=True),
    )
    op.bulk_insert(offers, [
        {"id": 1001, "name": "Демо-оффер A"},
        {"id": 1002, "name": "Демо-оффер B"},
        {"id": 1003, "name": "Демо-оффер C"},
    ])


def downgrade():
    op.drop_table("campaign_offers")
    op.drop_table("campaigns")
    op.drop_table("offers")
