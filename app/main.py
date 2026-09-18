from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routers import admin, auth, availability, bookings, checkins, payments, presence, services, staff_calendar

API_PREFIX = "/api/v1"
STATIC_DIR = Path(__file__).parent / "static"
OPENAPI_TAGS = [
    {"name": "system", "description": "Health checks and service status."},
    {"name": "auth", "description": "Staff login and authentication."},
    {"name": "services", "description": "Spa services and catalog endpoints."},
    {"name": "availability", "description": "Service availability and scheduling."},
    {"name": "bookings", "description": "Customer booking flows."},
    {"name": "payments", "description": "Daraja STK push, status queries, and callbacks."},
    {"name": "checkins", "description": "Guest check-in and visit tracking."},
    {"name": "presence", "description": "Staff presence and attendance."},
    {"name": "staff-calendar", "description": "Staff calendar and appointment views."},
    {"name": "admin", "description": "Administration and reconciliation endpoints."},
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Spa Booking API",
        summary="Booking, payments, check-ins, and reconciliation backend.",
        description=(
            "Use this Swagger UI to test the API from the browser. "
            "Daraja STK callbacks are received at `/api/v1/payments/callback`."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        swagger_ui_parameters={
            "displayRequestDuration": True,
            "persistAuthorization": True,
            "tryItOutEnabled": True,
            "docExpansion": "none",
        },
        servers=[
            {"url": "/", "description": "Current domain"},
        ],
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def docs_redirect() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.get("/swagger", include_in_schema=False)
    async def swagger_redirect() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api-test", include_in_schema=False)
    async def api_test_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "api-test.html")

    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(services.router, prefix=API_PREFIX)
    app.include_router(availability.router, prefix=API_PREFIX)
    app.include_router(bookings.router, prefix=API_PREFIX)
    app.include_router(payments.router, prefix=API_PREFIX)
    app.include_router(checkins.router, prefix=API_PREFIX)
    app.include_router(presence.router, prefix=API_PREFIX)
    app.include_router(staff_calendar.router, prefix=API_PREFIX)
    app.include_router(admin.router, prefix=API_PREFIX)

    return app


app = create_app()
