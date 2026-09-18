import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import Settings

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(
    *,
    staff_id: uuid.UUID,
    role: str,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    payload = {
        "sub": str(staff_id),
        "role": role,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise TokenError("Invalid authentication token") from exc

    if not payload.get("sub"):
        raise TokenError("Invalid authentication token")
    return payload
