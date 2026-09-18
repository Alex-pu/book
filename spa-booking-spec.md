# Spa Booking System — Build Spec

Stack: **FastAPI** + **PostgreSQL** + **Daraja (M-Pesa)** + **SMS API**, deployed on Ubuntu LTS behind an existing Cloudflare Tunnel. WordPress talks to this API via a shortcode widget.

This doc is meant to be handed to a coding assistant (e.g. Copilot) as the source of truth — folder layout, schema, and endpoint contracts are all defined so implementation doesn't require guessing business logic.

---

## 1. Project structure

```
spa-booking/
├── pyproject.toml
├── alembic.ini
├── .env.example
├── app/
│   ├── main.py                     # FastAPI app init, router mounting, CORS, startup
│   ├── config.py                   # Pydantic Settings — env vars
│   ├── database.py                 # SQLAlchemy engine/session, get_db dependency
│   │
│   ├── models/                     # SQLAlchemy ORM models (1 file per table group)
│   │   ├── staff.py                # Staff, StaffAvailability
│   │   ├── catalog.py              # Service
│   │   ├── booking.py              # Booking
│   │   ├── payment.py              # Payment, Disbursement
│   │   ├── checkin.py              # Checkin
│   │   └── notification.py         # NotificationLog
│   │
│   ├── schemas/                    # Pydantic request/response models, mirrors models/
│   │   ├── staff.py
│   │   ├── catalog.py
│   │   ├── booking.py
│   │   ├── payment.py
│   │   └── checkin.py
│   │
│   ├── routers/                    # API route handlers — thin, call services/
│   │   ├── auth.py                 # /auth/login (staff/admin only)
│   │   ├── services.py             # /services (public, list catalog)
│   │   ├── availability.py         # /availability (public, computed open slots)
│   │   ├── bookings.py             # /bookings (public create, staff manage)
│   │   ├── payments.py             # /payments/stk-push, /payments/callback (Daraja webhook)
│   │   ├── staff_calendar.py       # /staff/{id}/blocks (staff-only, block/unblock hours)
│   │   ├── checkins.py             # /checkins (staff-only)
│   │   ├── presence.py             # /presence/count (public, live occupancy)
│   │   └── admin.py                # /admin/disbursements, reconciliation views
│   │
│   ├── services/                   # Business logic — routers call these, not ORM directly
│   │   ├── scheduling.py           # slot computation, soft-lock, conflict checks
│   │   ├── booking_state.py        # booking state machine transitions
│   │   ├── daraja.py               # STK Push, C2B callback parsing, B2B disbursement calls
│   │   ├── fees.py                 # platform fee calculation
│   │   ├── sms.py                  # SMS API wrapper + message templates
│   │   └── presence.py             # occupancy counter logic
│   │
│   ├── core/
│   │   ├── security.py             # JWT issue/verify, password hashing
│   │   └── deps.py                 # get_current_staff, require_admin, etc.
│   │
│   └── jobs/                       # Background tasks (APScheduler or Celery — pick one)
│       ├── expire_soft_locks.py    # release unpaid bookings past lock TTL
│       ├── send_reminders.py       # SMS reminders N hours before appointment
│       └── nightly_disbursement.py # batch B2B forward to company till
│
├── migrations/                     # Alembic migrations
│   └── versions/
│
└── tests/
    ├── test_scheduling.py          # conflict/double-booking tests — critical, write first
    ├── test_daraja_callback.py     # payment callback idempotency tests
    └── test_booking_flow.py        # end-to-end: create → pay → confirm → checkin
```

**Notes for Copilot:**
- Routers must not contain business logic — they validate input, call a `services/` function, return the result. Keeps scheduling/payment logic testable without spinning up HTTP.
- Use Alembic for all schema changes, never hand-edit the DB.
- Pick APScheduler (simpler, in-process) unless you expect to scale to multiple workers, in which case use Celery + Redis.

---

## 2. Database schema (PostgreSQL DDL)

```sql
-- ============================
-- STAFF
-- ============================
CREATE TABLE staff (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       TEXT NOT NULL,
    phone           TEXT NOT NULL UNIQUE,
    role            TEXT NOT NULL DEFAULT 'masseuse',  -- 'masseuse' | 'admin'
    password_hash   TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Recurring or one-off open/blocked windows per staff member.
-- A row with is_available = FALSE represents an explicit block (time off, break).
CREATE TABLE staff_availability (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staff_id        UUID NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL,
    is_available    BOOLEAN NOT NULL DEFAULT TRUE,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_time > start_time)
);
CREATE INDEX idx_staff_availability_staff_time ON staff_availability (staff_id, start_time, end_time);

-- ============================
-- CATALOG
-- ============================
CREATE TABLE service (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,             -- 'Swedish Massage', 'Steam Bath', 'Facial'
    description     TEXT,
    duration_min    INT NOT NULL,              -- e.g. 60
    price_kes       NUMERIC(10,2) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Which staff can perform which service (many-to-many)
CREATE TABLE staff_service (
    staff_id        UUID NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    service_id      UUID NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    PRIMARY KEY (staff_id, service_id)
);

-- ============================
-- BOOKINGS
-- ============================
-- status lifecycle:
-- pending_payment -> confirmed -> checked_in -> completed
--                 -> expired (soft-lock timeout, no payment)
--                 -> cancelled (customer/staff cancelled after confirming)
CREATE TABLE booking (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id          UUID NOT NULL REFERENCES service(id),
    staff_id            UUID NOT NULL REFERENCES staff(id),
    customer_name       TEXT NOT NULL,
    customer_phone      TEXT NOT NULL,          -- also the M-Pesa STK push target
    start_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending_payment',
    lock_expires_at     TIMESTAMPTZ,             -- NULL once confirmed
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_time > start_time)
);

-- Prevents two CONFIRMED/CHECKED_IN bookings overlapping for the same staff member.
-- (Enforce the equivalent check in application code too, inside a transaction with
--  SELECT ... FOR UPDATE on the staff's booking rows, since exclusion constraints
--  need btree_gist and a tstzrange — add that migration if you want DB-level enforcement:)
-- CREATE EXTENSION IF NOT EXISTS btree_gist;
-- ALTER TABLE booking ADD CONSTRAINT no_overlapping_bookings
--   EXCLUDE USING gist (
--     staff_id WITH =,
--     tstzrange(start_time, end_time) WITH &&
--   ) WHERE (status IN ('confirmed','checked_in'));

CREATE INDEX idx_booking_staff_time ON booking (staff_id, start_time, end_time);
CREATE INDEX idx_booking_status ON booking (status);

-- ============================
-- PAYMENTS
-- ============================
-- One row per STK Push attempt against a booking.
CREATE TABLE payment (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id              UUID NOT NULL REFERENCES booking(id) ON DELETE CASCADE,
    checkout_request_id     TEXT UNIQUE,          -- Daraja STK Push identifier
    mpesa_receipt_number    TEXT UNIQUE,          -- from Daraja callback, once paid
    amount_kes              NUMERIC(10,2) NOT NULL,
    platform_fee_kes        NUMERIC(10,2) NOT NULL,
    net_to_forward_kes      NUMERIC(10,2) NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'initiated', -- initiated|success|failed|cancelled
    raw_callback_payload    JSONB,                -- store full Daraja callback for audits
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at            TIMESTAMPTZ
);
CREATE INDEX idx_payment_booking ON payment (booking_id);

-- B2B forwarding to the company till — one row per disbursement run
-- (batched nightly by default; can also be per-transaction).
CREATE TABLE disbursement (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_start        TIMESTAMPTZ NOT NULL,
    period_end          TIMESTAMPTZ NOT NULL,
    total_amount_kes    NUMERIC(10,2) NOT NULL,
    payment_count       INT NOT NULL,
    daraja_conversation_id TEXT,
    status              TEXT NOT NULL DEFAULT 'pending', -- pending|sent|confirmed|failed
    raw_response        JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ
);

-- Join table: which payments were included in which disbursement batch
CREATE TABLE disbursement_payment (
    disbursement_id     UUID NOT NULL REFERENCES disbursement(id) ON DELETE CASCADE,
    payment_id          UUID NOT NULL REFERENCES payment(id) ON DELETE CASCADE,
    PRIMARY KEY (disbursement_id, payment_id)
);

-- ============================
-- CHECK-IN / OCCUPANCY
-- ============================
CREATE TABLE checkin (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id      UUID REFERENCES booking(id),   -- NULL for walk-ins
    customer_name   TEXT,                           -- required if booking_id is NULL
    checked_in_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_out_at  TIMESTAMPTZ,
    checked_in_by   UUID NOT NULL REFERENCES staff(id)
);
CREATE INDEX idx_checkin_open ON checkin (checked_out_at) WHERE checked_out_at IS NULL;

-- ============================
-- NOTIFICATIONS
-- ============================
CREATE TABLE notification_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id      UUID REFERENCES booking(id),
    phone           TEXT NOT NULL,
    template        TEXT NOT NULL,   -- 'booking_confirmed' | 'reminder' | 'checkin_thanks' | ...
    body            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued', -- queued|sent|failed
    provider_ref    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 3. API contract

Base path: `/api/v1`. Public endpoints need no auth; Staff/Admin endpoints require `Authorization: Bearer <JWT>`.

### Public — Catalog & Availability

| Method | Path | Description |
|---|---|---|
| GET | `/services` | List active services (name, duration, price) |
| GET | `/availability?service_id=&date=` | Computed open slots for that service/date, across eligible staff |
| GET | `/presence/count` | `{ "current_count": int }` — live occupancy |

### Public — Booking & Payment

| Method | Path | Description |
|---|---|---|
| POST | `/bookings` | Create booking in `pending_payment`, soft-lock slot. Body: `service_id, staff_id, start_time, customer_name, customer_phone` → returns `booking_id` |
| POST | `/payments/stk-push` | Body: `booking_id`. Triggers Daraja STK Push to `customer_phone`. Returns `checkout_request_id` |
| POST | `/payments/callback` | **Daraja webhook** (not called by frontend). Verifies + records result, transitions booking to `confirmed` or releases lock on failure, fires SMS |
| GET | `/bookings/{id}/status` | Poll for frontend while waiting on STK push result |

### Staff — Calendar & Bookings

| Method | Path | Description |
|---|---|---|
| POST | `/auth/login` | Staff/admin login → JWT |
| GET | `/staff/{id}/bookings?date=` | Staff's bookings for a day/week |
| POST | `/staff/{id}/blocks` | Create a block (time off / break). Body: `start_time, end_time, note` |
| DELETE | `/staff/{id}/blocks/{block_id}` | Remove a block |
| PATCH | `/bookings/{id}/cancel` | Staff cancels a confirmed booking |

### Staff — Check-in

| Method | Path | Description |
|---|---|---|
| POST | `/checkins` | Body: `booking_id` (or `customer_name` for walk-in) → increments occupancy |
| PATCH | `/checkins/{id}/checkout` | Marks checked out → decrements occupancy |
| GET | `/checkins/open` | Currently checked-in list (for staff dashboard) |

### Admin — Reconciliation

| Method | Path | Description |
|---|---|---|
| GET | `/admin/disbursements` | List disbursement batches + status |
| POST | `/admin/disbursements/run` | Manually trigger a disbursement run (in addition to the nightly job) |
| GET | `/admin/payments?from=&to=` | Payment ledger for a date range |

---

## 4. Key business rules for Copilot to encode

1. **Slot locking**: `POST /bookings` must run inside a DB transaction, re-check for overlapping `confirmed`/`checked_in`/non-expired `pending_payment` bookings for that staff member before inserting, and set `lock_expires_at = now() + 5 minutes`. Use `SELECT ... FOR UPDATE` on the staff's rows in that window, or the `EXCLUDE` constraint above, to prevent race conditions from two simultaneous requests.
2. **Lock expiry job** (`jobs/expire_soft_locks.py`) runs every ~1 min: any `pending_payment` booking with `lock_expires_at < now()` and no successful payment → set `status = 'expired'`.
3. **Payment callback idempotency**: Daraja may retry the webhook. Use `checkout_request_id` (unique) to make `payments/callback` idempotent — if already processed, return 200 without reprocessing.
4. **Fee calculation** (`services/fees.py`): single function `calculate_fee(amount) -> (fee, net)` — keep the fee formula in one place since it'll likely change.
5. **Disbursement batching**: nightly job sums all `payment` rows with `status='success'` not yet in a `disbursement_payment` row, creates one `disbursement`, calls Daraja B2B, and links payments to it. Must be re-runnable safely if it fails partway (don't double-send).
6. **SMS triggers**: on booking confirmed, on reminder job (e.g. 2h before `start_time`), and optionally on checkout ("thanks for visiting"). Keep templates in `services/sms.py`, not inline in routers.
7. **Occupancy count** = `SELECT count(*) FROM checkin WHERE checked_out_at IS NULL`. Don't maintain a separate counter column — derive it, avoids drift.

---

## 5. Environment variables (`.env.example`)

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/spa_booking
JWT_SECRET=
JWT_EXPIRE_MINUTES=480

DARAJA_CONSUMER_KEY=
DARAJA_CONSUMER_SECRET=
DARAJA_SHORTCODE=            # your paybill
DARAJA_PASSKEY=
DARAJA_ENV=production        # or sandbox
DARAJA_CALLBACK_BASE_URL=    # your Cloudflare Tunnel public URL
DARAJA_B2B_RECEIVER_SHORTCODE=   # company till
DARAJA_INITIATOR_NAME=
DARAJA_INITIATOR_PASSWORD=

SMS_API_KEY=
SMS_API_SENDER_ID=

PLATFORM_FEE_PERCENT=5       # or flat fee — set to match services/fees.py logic
BOOKING_LOCK_MINUTES=5
```

---

## 6. Suggested build order

1. `models/` + Alembic migration for the full schema above
2. `services/scheduling.py` + `test_scheduling.py` — get double-booking prevention rock solid first
3. `routers/services.py`, `routers/availability.py`, `routers/bookings.py` (create only, no payment yet)
4. `services/daraja.py` STK Push + callback handling + `test_daraja_callback.py`
5. `services/sms.py` wired into the payment-confirmed path
6. `routers/staff_calendar.py` + `routers/checkins.py` + `routers/presence.py`
7. `jobs/nightly_disbursement.py` + `routers/admin.py`
8. WordPress shortcode widget last, once the API is stable
