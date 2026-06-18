#!/bin/bash
# Проверка, что на VPS запущена актуальная версия max2tg
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/max2tg}"
SERVICE="${SERVICE:-max2tg}"
GIT_USER="${GIT_USER:-max2tg}"

echo "=== Git (код на диске) ==="
cd "$APP_DIR"
sudo -u "$GIT_USER" git rev-parse --short HEAD
sudo -u "$GIT_USER" git log -1 --oneline

echo ""
echo "=== Формат стартового сообщения ==="
if grep -q 'MAX:</b> online' app/max_listener.py; then
  echo "OK: новый формат (MAX: online)"
else
  echo "FAIL: новый формат не найден в app/max_listener.py"
fi
if grep -q 'соединение восстановлено' app/max_listener.py; then
  echo "FAIL: старый текст «соединение восстановлено» всё ещё в коде"
else
  echo "OK: старый текст reconnect удалён"
fi

echo ""
echo "=== systemd ==="
systemctl cat "$SERVICE" 2>/dev/null | grep -E '^(WorkingDirectory|ExecStart)=' || echo "Сервис $SERVICE не найден"

echo ""
echo "=== Процесс бота ==="
PID=$(systemctl show -p MainPID "$SERVICE" --value 2>/dev/null || echo "0")
if [[ "$PID" =~ ^[0-9]+$ ]] && [[ "$PID" -gt 0 ]]; then
  echo "PID: $PID"
  readlink -f "/proc/$PID/cwd" 2>/dev/null || true
  tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null; echo
else
  echo "Сервис не запущен (MainPID=$PID)"
fi

echo ""
echo "=== Последние логи ==="
journalctl -u "$SERVICE" -n 15 --no-pager 2>/dev/null | grep -E 'max2tg version|Mute state|Connection error|Authorized' || \
  journalctl -u "$SERVICE" -n 8 --no-pager 2>/dev/null || true
