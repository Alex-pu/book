# Spa Booking API

FastAPI backend for spa bookings, payments, check-ins, and reconciliation.

## Local API Docs

Run the app:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Open the Swagger UI:

```text
http://127.0.0.1:8010/docs
```

The same docs page on the VPS domain will be:

```text
https://korebench.co.ke/docs
```

The Daraja callback URL is:

```text
https://korebench.co.ke/api/v1/payments/callback
```

Set this in `.env`:

```env
DARAJA_CALLBACK_BASE_URL=https://korebench.co.ke
```

## VPS Port

Run this app on port `8010` so it does not conflict with the existing apps:

```bash
cd ~/apps/spa-booking
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Cloudflare Tunnel should point `korebench.co.ke` and `www.korebench.co.ke` to:

```text
http://127.0.0.1:8010
```

## Git

The `.env` file is ignored so secrets are not committed. Commit code changes like this:

```bash
git status
git add .
git commit -m "Add Swagger API docs setup"
```
