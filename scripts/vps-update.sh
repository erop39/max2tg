#!/bin/bash
# Обновление бота на VPS из GitHub (без затрагивания .env)
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/max2tg}"
SERVICE="${SERVICE:-max2tg}"

cd "$APP_DIR"
sudo -u max2tg git pull origin main
sudo -u max2tg .venv/bin/pip install -r requirements.txt -q
sudo systemctl restart "$SERVICE"
sleep 2
sudo systemctl status "$SERVICE" --no-pager -l | head -20
