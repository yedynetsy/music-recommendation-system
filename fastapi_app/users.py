"""Registration, login, and logout using the existing Django user tables."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import authenticated_user, get_or_create_token, hash_password, verify_password
from .database import get_session
from .models import TokenRow, UserRow
from .schemas import LoginInput, RegisterInput, TokenResponse


router = APIRouter(prefix="/api/user", tags=["users"])


def bad_request(field: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={field: [message]})


@router.post("/register/", response_model=TokenResponse, status_code=201)
def register(payload: RegisterInput, session: Session = Depends(get_session)) -> TokenResponse | JSONResponse:
    existing = session.scalar(select(UserRow.id).where(UserRow.username == payload.username))
    if existing is not None:
        return bad_request("username", "A user with that username already exists.")
    user = UserRow(username=payload.username, password=hash_password(payload.password))
    session.add(user)
    try:
        session.flush()
        token = get_or_create_token(session, user.id)
        session.commit()
    except IntegrityError:
        session.rollback()
        if session.scalar(select(UserRow.id).where(UserRow.username == payload.username)) is None:
            raise
        return bad_request("username", "A user with that username already exists.")
    return TokenResponse(token=token.key, username=user.username)


@router.post("/login/", response_model=TokenResponse)
def login(payload: LoginInput, session: Session = Depends(get_session)) -> TokenResponse | JSONResponse:
    user = session.scalar(select(UserRow).where(UserRow.username == payload.username))
    if user is None or not user.is_active or not verify_password(payload.password, user.password):
        return bad_request("non_field_errors", "Invalid credentials.")
    user_id = user.id
    token = get_or_create_token(session, user_id)
    try:
        session.commit()
    except IntegrityError:
        # Another login may have created this user's one-to-one token first.
        session.rollback()
        token = session.scalar(select(TokenRow).where(TokenRow.user_id == user_id))
        if token is None:
            raise
    return TokenResponse(token=token.key, username=user.username)


@router.post("/logout/", status_code=204)
def logout(user: UserRow = Depends(authenticated_user),
           session: Session = Depends(get_session)) -> Response:
    session.execute(delete(TokenRow).where(TokenRow.user_id == user.id))
    session.commit()
    return Response(status_code=204)
