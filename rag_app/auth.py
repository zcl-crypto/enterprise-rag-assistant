from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.db import User


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hasher.verify(password, encoded)


def create_access_token(user_id: str, secret: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode({"sub": user_id, "exp": expires}, secret, algorithm="HS256")


def read_access_token(token: str, secret: str) -> str | None:
    try:
        subject = jwt.decode(token, secret, algorithms=["HS256"]).get("sub")
        return subject if isinstance(subject, str) else None
    except InvalidTokenError:
        return None


def seed_demo_users(session: Session, password: str) -> None:
    if session.scalar(select(User.id).limit(1)) is not None:
        return
    encoded = hash_password(password)
    session.add_all([
        User(username="admin", password_hash=encoded, role="admin"),
        User(username="employee", password_hash=encoded, role="employee"),
        User(username="procurement", password_hash=encoded, role="employee", department="采购部"),
    ])
