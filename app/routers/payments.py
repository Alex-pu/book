from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.deps import get_current_staff
from app.database import get_db
from app.models.staff import Staff
from app.schemas.payment import (
    DarajaAcceptedResponse,
    StkPushQueryResponse,
    StkPushRequest,
    StkPushResponse,
)
from app.services.daraja import DarajaClient, DarajaError, handle_stk_callback, initiate_booking_payment
from app.services.scheduling import SlotUnavailableError

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/stk-push", response_model=StkPushResponse)
async def stk_push(
    payload: StkPushRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StkPushResponse:
    try:
        async with db.begin():
            payment = await initiate_booking_payment(
                db,
                booking_id=payload.booking_id,
                settings=settings,
            )
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DarajaError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return StkPushResponse(
        payment_id=payment.id,
        checkout_request_id=payment.checkout_request_id,
    )


@router.post("/callback", response_model=DarajaAcceptedResponse)
async def payment_callback(
    payload: dict,
    db: AsyncSession = Depends(get_db),
) -> DarajaAcceptedResponse:
    async with db.begin():
        await handle_stk_callback(db, payload)

    return DarajaAcceptedResponse()


@router.post("/stk-push/{checkout_request_id}/query", response_model=StkPushQueryResponse)
async def query_stk_push(
    checkout_request_id: str,
    settings: Settings = Depends(get_settings),
    current_staff: Staff = Depends(get_current_staff),
) -> StkPushQueryResponse:
    try:
        result = await DarajaClient(settings).query_stk_push(
            checkout_request_id=checkout_request_id
        )
    except DarajaError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return StkPushQueryResponse(
        checkout_request_id=result.checkout_request_id,
        result_code=result.result_code,
        result_description=result.result_description,
        response_code=result.response_code,
        response_description=result.response_description,
        raw_response=result.raw_response,
    )
