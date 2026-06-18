#!/bin/bash
# Обновление бота на VPS из GitHub (без затрагивания .env)
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/max2tg}"
SERVICE="${SERVICE:-max2tg}"
GIT_USER="${GIT_USER:-max2tg}"

cd "$APP_DIR"

echo "==> Fetching origin/main..."
sudo -u "$GIT_USER" git fetch origin main

echo "==> Resetting to origin/main (local code changes will be discarded, .env is safe)..."
sudo -u "$GIT_USER" git reset --hard origin/main

echo "==> Current revision:"
sudo -u "$GIT_USER" git rev-parse --short HEAD

echo "==> Checking startup message format in code..."
grep -q '_startup_message' app/max_listener.py && grep -q 'MAX:</b> online' app/max_listener.py || {
  echo "ERROR: app/max_listener.py does not contain new startup format." >&2
  exit 1
}

echo "==> Installing dependencies..."
sudo -u "$GIT_USER" .venv/bin/pip install -r requirements.txt -q

echo "==> Restarting $SERVICE..."
sudo systemctl restart "$SERVICE"
sleep 2
sudo systemctl status "$SERVICE" --no-pager -l | head -20

echo "==> Running deploy verification..."
bash "$APP_DIR/scripts/verify-deploy.sh" || true
