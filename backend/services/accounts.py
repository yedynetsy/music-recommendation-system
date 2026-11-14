"""Create the first staff account from a trusted local terminal."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.security import hash_password
from backend.database import SessionFactory
from backend.models import UserRow
from backend.schemas import RegisterInput


def create_staff(username: str, password: str) -> None:
    validated = RegisterInput(username=username, password=password, password_confirm=password)
    with SessionFactory() as session:
        if session.scalar(select(UserRow.id).where(UserRow.username == validated.username)) is not None:
            raise ValueError("Username already exists.")
        session.add(UserRow(username=validated.username, password=hash_password(password), is_staff=True))
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise ValueError("Could not create staff user; username may already exist.") from error
