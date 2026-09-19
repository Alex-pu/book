#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
source .venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8010}"
