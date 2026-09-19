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

### LAN access

To serve the app to other devices on the same network:

```bash
bash scripts/run-lan.sh
```

Open `http://<server-lan-ip>:8010/booking-console` from a LAN device. Allow TCP port `8010` through the server firewall if needed. The app still uses the `DATABASE_URL` from `.env`.

### Daily PostgreSQL backups

The backup script uses `pg_dump`, stores compressed custom-format dumps, and removes dumps older than 30 days:

```bash
chmod +x scripts/backup-postgres.sh
set -a; source .env; set +a
scripts/backup-postgres.sh
```

Schedule it daily with cron:

```cron
0 2 * * * cd /home/alec/apps/spa-booking && set -a && . .env && set +a && /home/alec/apps/spa-booking/scripts/backup-postgres.sh >> /home/alec/backups/spa-booking-backup.log 2>&1
```

### Payment fallback

Each booking displays the Daraja PayBill shortcode and a booking account reference. If STK does not arrive, the guest can pay using those values. The widget can query the callback result using the phone number and account reference; it never marks a payment as paid itself. Until Daraja's callback is recorded, it shows that the guest should try again later. Confirmed guests can search with their phone number and download a PDF ticket for reception.
