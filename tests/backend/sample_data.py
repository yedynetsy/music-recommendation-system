import numpy as np
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.models import TrackRow
from recommendations.inference import ServingModel


ADMIN_HEADERS = {"Authorization": f"Token {'a' * 40}"}
USER_HEADERS = {"Authorization": f"Token {'u' * 40}"}

FIRST = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"
THIRD = "33333333-3333-4333-8333-333333333333"
FUTURE = "44444444-4444-4444-8444-444444444444"
CUTOFF = datetime(2009, 1, 2, tzinfo=timezone.utc)


def serving_model() -> ServingModel:
    return ServingModel(
        [FIRST, SECOND, THIRD],
        np.array([[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]], dtype=np.float32),
        np.array([2, 5, 1]), 10.0, 0.05, "test-model", CUTOFF.isoformat(),
    )


def add_tracks(engine) -> None:
    with Session(engine) as session:
        session.add_all([
            TrackRow(mbid=FIRST, name="Same Name", artist_name="Artist A"),
            TrackRow(mbid=SECOND, name="Same Name", artist_name="Artist B"),
            TrackRow(mbid=THIRD, name="Other", artist_name=None),
        ])
        session.commit()
