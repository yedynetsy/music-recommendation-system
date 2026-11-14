"""Create the first staff account from a trusted local terminal."""

from getpass import getpass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .auth import hash_password
from .database import SessionFactory
from .models import UserRow
from .schemas import RegisterInput


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


def main() -> None:
    username = input("Staff username: ").strip()
    password = getpass("Password: ")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords do not match.")
    try:
        create_staff(username, password)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print("Staff account created.")


if __name__ == "__main__":
    main()
