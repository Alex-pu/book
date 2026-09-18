import uuid

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    staff_id: uuid.UUID
    role: str
    expires_in_minutes: int
