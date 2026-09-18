from datetime import timedelta
from uuid import uuid4

import pytest

from app.config import Settings
from app.core.security import TokenError, create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_verification() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", password_hash) is True
    assert verify_password("wrong password", password_hash) is False


def test_access_token_round_trip() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/test",
        JWT_SECRET="test-secret",
    )
    staff_id = uuid4()

    token = create_access_token(staff_id=staff_id, role="admin", settings=settings)
    payload = decode_access_token(token, settings)

    assert payload["sub"] == str(staff_id)
    assert payload["role"] == "admin"


def test_expired_access_token_is_rejected() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/test",
        JWT_SECRET="test-secret",
    )
    token = create_access_token(
        staff_id=uuid4(),
        role="masseuse",
        settings=settings,
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(TokenError):
        decode_access_token(token, settings)
