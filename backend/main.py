"""Create the API and register its routes and exception handlers."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from backend import exception_handlers
from backend.routes import albums, artists, auth, listens, onboarding, recommendations, tracks
from backend.services.recommendations import RecommendationCatalogMismatch, SimilarTrackUnavailable


app = FastAPI(title="Music Recommendation API")
for route_module in (auth, albums, tracks, listens, recommendations, onboarding, artists):
    app.include_router(route_module.router)

app.add_exception_handler(albums.UnknownArtistError, exception_handlers.unknown_album_artist)
app.add_exception_handler(RequestValidationError, exception_handlers.input_validation_error)
app.add_exception_handler(RecommendationCatalogMismatch, exception_handlers.catalog_mismatch)
app.add_exception_handler(SimilarTrackUnavailable, exception_handlers.similar_track_unavailable)
