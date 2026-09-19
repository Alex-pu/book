import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.security import TokenError, decode_access_token
from app.database import get_db
from app.models.staff import Staff

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_staff(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Staff:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials, settings)
        staff_id = uuid.UUID(payload["sub"])
    except (TokenError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    staff = await db.get(Staff, staff_id)
    if staff is None or not staff.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff account is inactive or missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return staff


async def require_admin(current_staff: Staff = Depends(get_current_staff)) -> Staff:
    if current_staff.role not in {"admin", "spa_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or spa admin access required",
        )
    return current_staff


async def require_super_admin(current_staff: Staff = Depends(get_current_staff)) -> Staff:
    if current_staff.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_staff


def ensure_staff_scope(current_staff: Staff, staff_id: uuid.UUID) -> None:
    if current_staff.role == "admin" or current_staff.id == staff_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot access another staff member's calendar",
    )
