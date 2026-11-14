"""Create a staff account through the backend's trusted terminal command."""

from getpass import getpass

from fastapi_app.create_staff import create_staff


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
