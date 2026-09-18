from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models.staff import Staff
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    row = await db.execute(select(Staff).where(Staff.email == payload.email))
    staff = row.scalar_one_or_none()
    if staff is None or not staff.is_active or not verify_password(payload.password, staff.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(staff_id=staff.id, role=staff.role, settings=settings)
    return TokenResponse(
        access_token=token,
        staff_id=staff.id,
        role=staff.role,
        expires_in_minutes=settings.jwt_expire_minutes,
    )
