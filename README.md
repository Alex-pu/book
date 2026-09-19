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

Daraja STK Push also requires these values in `.env`:

```env
DARAJA_CONSUMER_KEY=your_daraja_consumer_key
DARAJA_CONSUMER_SECRET=your_daraja_consumer_secret
DARAJA_SHORTCODE=your_paybill_or_till_shortcode
DARAJA_PASSKEY=your_shortcode_passkey
DARAJA_ENV=production
DARAJA_CALLBACK_BASE_URL=https://your-public-https-domain
```

`DARAJA_CALLBACK_BASE_URL` must be publicly reachable over HTTPS. `localhost` will not receive Safaricom callbacks. For local testing, use a secure tunnel and set its HTTPS URL here, then restart the API.

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

### Push from Windows

From PowerShell in the project directory:

```powershell
.\scripts\push-to-github.ps1 "Describe the change"
```

The script runs the tests, stages all changes except ignored files such as `.env`, commits, and pushes `main`.

### Update the VPS

On the VPS:

```bash
cd ~/apps/spa-booking
bash scripts/pull-on-vps.sh spa-booking
```

The script fast-forward pulls `main`, updates the virtualenv, runs Alembic migrations, and restarts the supplied systemd service. Omit `spa-booking` when the app is managed another way.

### Payment fallback

Each booking displays the Daraja PayBill shortcode and a booking account reference. If STK does not arrive, the guest can pay using those values. Reception should verify the M-Pesa receipt and use **Confirm Paid** in the authenticated booking console. Confirmed guests can search with their phone number and download a PDF ticket for reception.
