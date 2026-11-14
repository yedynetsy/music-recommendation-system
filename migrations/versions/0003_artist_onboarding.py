"""Store application users' chosen artist MusicBrainz IDs.

Revision ID: 0003_artist_onboarding
Revises: 0002_recommendations
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_artist_onboarding"
down_revision = "0002_recommendations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_artist_preference",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users_user.id"), primary_key=True),
        sa.Column("artist_mbid", sa.String(36), primary_key=True),
    )
    op.create_index("ix_tracks_track_artist_mbid", "tracks_track", ["artist_mbid"])


def downgrade() -> None:
    op.drop_index("ix_tracks_track_artist_mbid", "tracks_track")
    op.drop_table("recommendation_artist_preference")
