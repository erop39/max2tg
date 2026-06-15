# Памятка: обновление токена Max и перезапуск бота

Краткая инструкция для VPS (`systemd`, путь `/opt/max2tg`).

---

## Когда обновлять токен

- В логах: `Max auth timeout`, `Max auth rejected`, бесконечные `Reconnecting...`
- Сообщения из Max перестали приходить в Telegram
- Вы вышли и снова вошли в [web.max.ru](https://web.max.ru)
- Прошло много времени с последнего обновления (профилактика)

---

## Шаг 1. Получить новый токен в браузере

1. Откройте **https://web.max.ru** и **войдите** в аккаунт
2. Нажмите **F12** (DevTools)
3. Вкладка **Application** (Chrome) или **Storage** (Firefox)
4. Слева: **Local Storage** → `https://web.max.ru`
5. Скопируйте значения **без кавычек**:

| Ключ в браузере      | Переменная в `.env` |
|----------------------|---------------------|
| `__oneme_auth`       | `MAX_TOKEN`         |
| `__oneme_device_id`  | `MAX_DEVICE_ID`     |

> Не делитесь этими значениями — это полный доступ к вашему Max.

---

## Шаг 2. Подключиться к VPS

```bash
ssh user@ВАШ_IP
```

---

## Шаг 3. Отредактировать `.env`

```bash
sudo -u max2tg nano /opt/max2tg/.env
```

Замените строки (пример):

```env
MAX_TOKEN=новое_значение___oneme_auth
MAX_DEVICE_ID=новое_значение___oneme_device_id
```

Сохранить: `Ctrl+O` → `Enter` → выйти: `Ctrl+X`

Проверить права (должно быть `-rw-------`):

```bash
ls -la /opt/max2tg/.env
```

При необходимости:

```bash
sudo chown max2tg:max2tg /opt/max2tg/.env
sudo chmod 600 /opt/max2tg/.env
```

---

## Шаг 4. Перезапустить бота

```bash
sudo systemctl restart max2tg
```

Проверить статус:

```bash
sudo systemctl status max2tg
```

Должно быть: `Active: active (running)`

---

## Шаг 5. Проверить логи

Последние 20 строк:

```bash
sudo journalctl -u max2tg -n 20 --no-pager
```

Успешный запуск:

```
Authorized! my_id=...
Telegram bot ready: @egormaxbot
```

Логи в реальном времени:

```bash
sudo journalctl -u max2tg -f
```

Выход: `Ctrl+C`

Файл на диске:

```bash
tail -f /opt/max2tg/logs/max2tg.log
```

---

## Всё одной цепочкой

После правки `.env` в nano:

```bash
sudo systemctl restart max2tg && sleep 2 && sudo journalctl -u max2tg -n 20 --no-pager
```

---

## Полезные команды

| Действие | Команда |
|----------|---------|
| Перезапуск | `sudo systemctl restart max2tg` |
| Остановка | `sudo systemctl stop max2tg` |
| Запуск | `sudo systemctl start max2tg` |
| Статус | `sudo systemctl status max2tg` |
| Логи (live) | `sudo journalctl -u max2tg -f` |
| Редактировать .env | `sudo -u max2tg nano /opt/max2tg/.env` |
| Включить ответы в Max | в `.env`: `REPLY_ENABLED=true` → restart |
| Отключить отладку | в `.env`: `DEBUG=false` → restart |

---

## Алиасы (опционально)

Добавьте в `~/.bashrc` на VPS:

```bash
alias max2tg-env='sudo -u max2tg nano /opt/max2tg/.env'
alias max2tg-restart='sudo systemctl restart max2tg && sleep 2 && sudo journalctl -u max2tg -n 15 --no-pager'
alias max2tg-status='sudo systemctl status max2tg'
alias max2tg-logs='sudo journalctl -u max2tg -f'
```

Применить:

```bash
source ~/.bashrc
```

Использование:

```bash
max2tg-env        # открыть .env
max2tg-restart    # перезапуск + логи
max2tg-logs       # смотреть логи
```

---

## Если не помогло

1. Убедитесь, что в браузере вы **залогинены** в Max перед копированием токена
2. Скопируйте токен **целиком**, без пробелов в начале/конце
3. Обновите **оба** значения: `MAX_TOKEN` и `MAX_DEVICE_ID`
4. Проверьте, что Telegram-бот жив: в логах `Telegram bot ready`
5. Отправьте тестовое сообщение **от другого человека** в Max (свои не пересылаются)

Диагностика:

```bash
sudo journalctl -u max2tg -n 50 --no-pager
```

Ручной запуск (для отладки, остановите сервис сначала):

```bash
sudo systemctl stop max2tg
sudo -u max2tg bash -c 'cd /opt/max2tg && .venv/bin/python -m app.main'
```

Вернуть сервис: `Ctrl+C`, затем `sudo systemctl start max2tg`

---

## Безопасность

- Не отправляйте `.env` и токены в мессенджеры, почту, скриншоты
- Не коммитьте `.env` в git
- На VPS: только `chmod 600` и владелец `max2tg`
