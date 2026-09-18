import uuid

from pydantic import BaseModel, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    phone: str | None = Field(default=None, min_length=7, max_length=64)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("phone", "email")
    @classmethod
    def strip_optional_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.lower()
        if "@" not in value:
            raise ValueError("Email must be valid")
        return value

    @model_validator(mode="after")
    def require_identifier(self) -> "LoginRequest":
        if not self.phone and not self.email:
            raise ValueError("Either phone or email is required")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    staff_id: uuid.UUID
    role: str
    expires_in_minutes: int


class AdminBootstrapRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="Admin", min_length=1, max_length=200)
    phone: str | None = Field(default=None, min_length=7, max_length=64)

    @field_validator("email")
    @classmethod
    def normalize_admin_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("Email must be valid")
        return value

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def strip_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AdminBootstrapResponse(BaseModel):
    staff_id: uuid.UUID
    email: str
    role: str
