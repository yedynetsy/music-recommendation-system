"""HTTP error translation for API routes."""

from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.routes.albums import UnknownArtistError
from backend.services.recommendations import RecommendationCatalogMismatch, SimilarTrackUnavailable


async def unknown_album_artist(request: Request, error: UnknownArtistError):
    return JSONResponse(status_code=400, content={"artist": ["Invalid artist ID."]})


async def input_validation_error(request: Request, error: RequestValidationError):
    is_api_route = request.url.path.startswith(("/api/artists/", "/api/albums/", "/api/user/"))
    if request.method not in {"POST", "PUT", "PATCH"} or not is_api_route:
        return await request_validation_exception_handler(request, error)
    details: dict[str, list[str]] = {}
    for issue in error.errors():
        field = str(issue["loc"][-1]) if len(issue["loc"]) > 1 else "non_field_errors"
        details.setdefault(field, []).append(issue["msg"])
    return JSONResponse(status_code=400, content=details)


async def catalog_mismatch(request: Request, error: RecommendationCatalogMismatch):
    return JSONResponse(status_code=503, content={
        "detail": "Recommendation model and track catalog differ."})


async def similar_track_unavailable(request: Request, error: SimilarTrackUnavailable):
    return JSONResponse(status_code=404, content={"detail": error.detail})
