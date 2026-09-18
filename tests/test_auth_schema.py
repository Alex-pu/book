import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest


def test_login_request_accepts_email_password_only() -> None:
    payload = LoginRequest(email=" KAMAUA175@GMAIL.COM ", password="ongod100")

    assert payload.email == "kamaua175@gmail.com"
    assert payload.password == "ongod100"


def test_login_request_rejects_phone_field() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(
            email="kamaua175@gmail.com",
            phone="254704813341",
            password="ongod100",
        )
