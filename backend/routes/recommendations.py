"""Personalized and item-to-item recommendation routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_session
from backend.dependencies import get_serving_model
from backend.models import UserRow
from backend.schemas import RecommendationResponse
from backend.security import authenticated_user
from backend.services.recommendations import recommend_for_user, recommend_similar
from recommendations.inference import ServingModel


router = APIRouter(tags=["recommendations"])


@router.get("/api/recommendations/", response_model=RecommendationResponse)
def recommend_tracks(limit: int = Query(10, ge=1, le=50),
                     user: UserRow = Depends(authenticated_user),
                     model: ServingModel = Depends(get_serving_model),
                     session: Session = Depends(get_session)) -> RecommendationResponse:
    return recommend_for_user(session, user.id, model, limit)


@router.get("/api/tracks/{track_mbid}/similar/", response_model=RecommendationResponse)
def similar_tracks(track_mbid: UUID, limit: int = Query(10, ge=1, le=50),
                   user: UserRow = Depends(authenticated_user),
                   model: ServingModel = Depends(get_serving_model),
                   session: Session = Depends(get_session)) -> RecommendationResponse:
    return recommend_similar(session, user.id, model, str(track_mbid), limit)
