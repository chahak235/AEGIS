"""Command-line helper for tasks you do before anyone can log in.

Create the first admin (run from the backend folder, virtual environment active):

    python -m app.cli create-user admin --role admin

It asks for the password without showing it on screen.
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app import audit
from app.db import SessionLocal
from app.models import User
from app.security import MIN_PASSWORD_LENGTH, hash_password


def create_user(username: str, role: str) -> None:
    username = username.strip().lower()
    password = getpass.getpass(f"Password for {username} (min {MIN_PASSWORD_LENGTH} chars): ")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"Password too short (minimum {MIN_PASSWORD_LENGTH} characters).")
    if password != getpass.getpass("Type it again: "):
        sys.exit("Passwords do not match.")
    with SessionLocal() as session:
        if session.scalars(select(User).where(User.username == username)).first():
            sys.exit(f"User '{username}' already exists.")
        session.add(User(username=username, password_hash=hash_password(password),
                         role=role, is_active=True))
        audit.record(session, actor="cli", action="user.created",
                     target_type="user", target_id=username, details={"role": role})
        session.commit()
    print(f"Created {role} '{username}'. Log in at http://127.0.0.1:8000/docs -> Authorize.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="create a user (asks for the password)")
    create.add_argument("username")
    create.add_argument("--role", choices=["analyst", "admin"], default="analyst")
    args = parser.parse_args()
    if args.command == "create-user":
        create_user(args.username, args.role)


if __name__ == "__main__":
    main()
