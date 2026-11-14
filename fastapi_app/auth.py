"""Token authentication and PBKDF2 password compatibility."""

import base64
import hashlib
import secrets
import string
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_session
from .models import TokenRow, UserRow


PASSWORD_ITERATIONS = 1_000_000
SALT_ALPHABET = string.ascii_letters + string.digits


def hash_password(password: str) -> str:
    salt = "".join(secrets.choice(SALT_ALPHABET) for _ in range(22))
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iteration_text, salt, expected = encoded.split("$")
        iterations = int(iteration_text)
        if algorithm != "pbkdf2_sha256" or not 1 <= iterations <= 10_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
        return secrets.compare_digest(base64.b64encode(actual).decode(), expected)
    except (TypeError, ValueError):
        return False


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
