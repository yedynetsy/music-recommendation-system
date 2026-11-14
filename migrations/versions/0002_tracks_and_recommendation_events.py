"""Add track catalog, app listens, and recommendation exposures.

Revision ID: 0002_recommendations
Revises: 0001_catalog_schema
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_recommendations"
down_revision = "0001_catalog_schema"
branch_labels = None
depends_on = None


id_type = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    op.create_table(
        "tracks_track",
        sa.Column("mbid", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("artist_mbid", sa.String(36), nullable=True),
        sa.Column("artist_name", sa.Text(), nullable=True),
    )
    op.create_table(
        "recommendation_listen",
        sa.Column("id", id_type, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users_user.id"), nullable=False),
        sa.Column("track_mbid", sa.String(36), sa.ForeignKey("tracks_track.mbid"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recommendation_listen_user_id", "recommendation_listen", ["user_id"])
    op.create_table(
        "recommendation_exposure",
        sa.Column("id", id_type, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users_user.id"), nullable=False),
        sa.Column("track_mbid", sa.String(36), sa.ForeignKey("tracks_track.mbid"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recommendation_exposure_user_id", "recommendation_exposure", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_exposure_user_id", "recommendation_exposure")
    op.drop_table("recommendation_exposure")
    op.drop_index("ix_recommendation_listen_user_id", "recommendation_listen")
    op.drop_table("recommendation_listen")
    op.drop_table("tracks_track")
