"""Password hashing, session tokens and the session cookie. Secrets come from backend/.env only."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Response
from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

COOKIE_NAME = "vatrexz_session"
SESSION_HOURS = 12


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd.verify(password, password_hash)
    except Exception:
        return False


def new_session() -> tuple[str, datetime]:
    return str(uuid.uuid4()), datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)


def create_token(user_id: str, session_id: str, expires_at: datetime) -> str:
    payload = {"sub": user_id, "sid": session_id, "exp": expires_at, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=os.environ.get("COOKIE_SECURE", "true").lower() == "true",
        samesite="lax",
        max_age=SESSION_HOURS * 3600,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
