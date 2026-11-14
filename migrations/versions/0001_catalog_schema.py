"""Create catalog, user, and token tables.

Revision ID: 0001_catalog_schema
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_catalog_schema"
down_revision = None
branch_labels = None
depends_on = None


id_type = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    op.create_table(
        "artists_artist",
        sa.Column("id", id_type, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users_user",
        sa.Column("id", id_type, primary_key=True),
        sa.Column("password", sa.String(128), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("username", sa.String(150), nullable=False, unique=True),
        sa.Column("first_name", sa.String(150), nullable=False),
        sa.Column("last_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("is_staff", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("date_joined", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "albums_album",
        sa.Column("id", id_type, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("artist_id", sa.BigInteger(), sa.ForeignKey("artists_artist.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "authtoken_token",
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users_user.id"), nullable=False, unique=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("authtoken_token")
    op.drop_table("albums_album")
    op.drop_table("users_user")
    op.drop_table("artists_artist")
