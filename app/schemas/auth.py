import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip()
        value = value.lower()
        if "@" not in value:
            raise ValueError("Email must be valid")
        return value


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

    model_config = ConfigDict(extra="forbid")

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


class AdminBootstrapResponse(BaseModel):
    staff_id: uuid.UUID
    email: str
    role: str
