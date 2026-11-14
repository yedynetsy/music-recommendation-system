"""Shared Django-token authentication during the API migration."""

import os
import secrets
from datetime import datetime, timezone

from django.contrib.auth.hashers import check_password, make_password
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_session
from .models import TokenRow, UserRow


def _use_django_hashers() -> None:
    # Keep existing Django password hashes valid until user storage is migrated.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def hash_password(password: str) -> str:
    _use_django_hashers()
    return make_password(password)


def verify_password(password: str, encoded: str) -> bool:
    _use_django_hashers()
    return check_password(password, encoded)


def get_or_create_token(session: Session, user_id: int) -> TokenRow:
    token = session.scalar(select(TokenRow).where(TokenRow.user_id == user_id))
    if token is None:
        token = TokenRow(key=secrets.token_hex(20), user_id=user_id,
                         created=datetime.now(timezone.utc))
        session.add(token)
    return token


def authenticated_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> UserRow:
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "token":
        raise HTTPException(401, detail="Authentication credentials were not provided.",
                            headers={"WWW-Authenticate": "Token"})
    user = session.scalar(
        select(UserRow).join(TokenRow, UserRow.id == TokenRow.user_id).where(TokenRow.key == parts[1])
    )
    if user is None or not user.is_active:
        raise HTTPException(401, detail="Invalid token.", headers={"WWW-Authenticate": "Token"})
    return user


def require_admin(user: UserRow = Depends(authenticated_user)) -> None:
    if not user.is_staff:
        raise HTTPException(403, detail="You do not have permission to perform this action.")
