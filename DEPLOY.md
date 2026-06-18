# Безопасный деплой max2tg на VPS (24/7)

Инструкция для **вашей версии** с плагинами (`app/hooks.py`, `app/plugins/`).

Цель: бот работает постоянно, а `.env` с токенами доступен **только вам**.

---

## Что защищаем

| Секрет | Риск при утечке |
|--------|-----------------|
| `MAX_TOKEN` + `MAX_DEVICE_ID` | Полный доступ к аккаунту Max |
| `TG_BOT_TOKEN` | Управление вашим Telegram-ботом |

`.env` **никогда** не коммитится в git (уже в `.gitignore`) и **не попадает** в Docker-образ (`.dockerignore`).

---

## 1. Подготовка VPS

Рекомендуется VPS в **РФ/СНГ** — с части зарубежных серверов Max не авторизуется.

```bash
# Обновление системы (Ubuntu/Debian)
sudo apt update && sudo apt upgrade -y

# Отдельный пользователь только для бота (не root)
sudo adduser --disabled-password --gecos "" max2tg
```

### SSH: доступ только вам

На **вашем ПК** (если ещё нет ключа):

```bash
ssh-keygen -t ed25519 -C "your-email"
```

Скопируйте ключ на VPS:

```bash
ssh-copy-id root@ВАШ_IP
```

На VPS отредактируйте `/etc/ssh/sshd_config`:

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart sshd
```

Дальше входите как обычный пользователь с sudo, не по паролю.

---

## 2. Загрузка с GitHub

Репозиторий: **https://github.com/erop39/max2tg** (private)

### Первичная установка на VPS

```bash
sudo mkdir -p /opt/max2tg
sudo chown max2tg:max2tg /opt/max2tg

# HTTPS (запросит логин GitHub + Personal Access Token вместо пароля)
sudo -u max2tg git clone https://github.com/erop39/max2tg.git /opt/max2tg

# или SSH, если ключ max2tg добавлен в GitHub → Settings → SSH keys
# sudo -u max2tg git clone git@github.com:erop39/max2tg.git /opt/max2tg
```

**Вариант B — архив** (если git на VPS не настроен): см. ниже в старом разделе tar.

### Обновление кода на VPS (без потери .env)

```bash
sudo bash /opt/max2tg/scripts/vps-update.sh
```

Или вручную:

```bash
cd /opt/max2tg
sudo -u max2tg git fetch origin main
sudo -u max2tg git reset --hard origin/main   # .env не затрагивается
sudo -u max2tg .venv/bin/pip install -r requirements.txt -q
sudo systemctl restart max2tg
```

> **Важно:** не используйте `git pull` — при расхождении веток он падает и код **не обновляется**.
>
> **Git от root:** если видите `dubious ownership in repository` — не запускайте `git` от root.
> Используйте `sudo -u max2tg git ...` (как выше) или скрипт `vps-update.sh`.
>
> Проверка после обновления:
> ```bash
> grep "MAX:</b> online" /opt/max2tg/app/max_listener.py
> journalctl -u max2tg -n 20 | grep "max2tg version"
> ```

Файл `.env` при обновлении **не меняется**.

---

## 2b. Загрузка архивом (альтернатива)

На Windows (PowerShell):

```powershell
cd d:\appz
# .env в архив НЕ включаем
tar -czf max2tg-deploy.tar.gz --exclude=max2tg/.env --exclude=max2tg/.venv --exclude=max2tg/logs max2tg
scp max2tg-deploy.tar.gz user@ВАШ_IP:/tmp/
```

На VPS:

```bash
sudo mkdir -p /opt/max2tg
sudo tar -xzf /tmp/max2tg-deploy.tar.gz -C /opt --strip-components=0
sudo chown -R max2tg:max2tg /opt/max2tg
```

---

## 3. Создание `.env` только на сервере

**Не копируйте `.env` через публичные каналы.** Создайте файл прямо на VPS:

```bash
sudo -u max2tg nano /opt/max2tg/.env
```

Вставьте значения (как на локальной машине), сохраните.

### Права на файл — критично

```bash
sudo chown max2tg:max2tg /opt/max2tg/.env
sudo chmod 600 /opt/max2tg/.env
```

Проверка:

```bash
ls -la /opt/max2tg/.env
# -rw------- 1 max2tg max2tg ... .env
```

Только пользователь `max2tg` может читать файл. Root на VPS технически может — поэтому VPS должен быть **только у вас** (не shared-хостинг, не «другу на сервер»).

Дополнительно запретите group/other на каталог:

```bash
sudo chmod 750 /opt/max2tg
```

---

## 4. Запуск: Docker (рекомендуется)

```bash
cd /opt/max2tg
sudo -u max2tg cp .env.example .env   # если ещё не создали
sudo -u max2tg nano .env
sudo chmod 600 /opt/max2tg/.env
sudo chown max2tg:max2tg /opt/max2tg/.env

# Docker от имени пользователя max2tg или через sudo
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker max2tg   # опционально, перелогиниться

cd /opt/max2tg
docker compose up -d --build
```

Секреты читаются из `env_file: .env` на хосте — **не** прописывайте токены в `docker-compose.yml`.

Проверка:

```bash
docker compose logs -f
```

Бот **не открывает входящих портов** — firewall можно оставить закрытым (только SSH).

```bash
sudo ufw allow OpenSSH
sudo ufw enable
```

---

## 5. Запуск: systemd (без Docker)

```bash
cd /opt/max2tg
sudo -u max2tg python3 -m venv .venv
sudo -u max2tg .venv/bin/pip install -r requirements.txt

sudo cp deploy/max2tg.service.example /etc/systemd/system/max2tg.service
sudo nano /etc/systemd/system/max2tg.service
# Проверьте: User=max2tg, WorkingDirectory=/opt/max2tg, EnvironmentFile=/opt/max2tg/.env

sudo -u max2tg mkdir -p /opt/max2tg/logs /opt/max2tg/debug

sudo systemctl daemon-reload
sudo systemctl enable --now max2tg
sudo journalctl -u max2tg -f
```

---

## 6. Чеклист безопасности

- [ ] `.env` с правами `600`, владелец `max2tg`
- [ ] `.env` не в git, не в Docker-образе, не в скриншотах
- [ ] SSH только по ключу, пароль отключён
- [ ] VPS не используется посторонними
- [ ] `DEBUG=false` на продакшене (меньше утечек в логах)
- [ ] Логи `logs/max2tg.log` не содержат токены (в коде есть маскирование)
- [ ] Периодически обновляйте `MAX_TOKEN` при истечении сессии Max

---

## 7. Обновление бота

```bash
sudo bash /opt/max2tg/scripts/vps-update.sh
```

Или с ПК после `git push`:

```bash
ssh user@ВАШ_IP 'sudo bash /opt/max2tg/scripts/vps-update.sh'
```

Файл `.env` при обновлении кода **не перезаписывается**.

Подробная памятка по обновлению токена Max: **[TOKEN_UPDATE.md](TOKEN_UPDATE.md)**

---

## 8. Если VPS взломают

1. Немедленно смените `MAX_TOKEN` (перелогин в web.max.ru → новый `__oneme_auth`)
2. Отзовите бота через @BotFather → `/revoke` → новый `TG_BOT_TOKEN`
3. Пересоздайте VPS с нуля

---

## Переменные для продакшена

```env
DEBUG=false
REPLY_ENABLED=true
PLUGINS_ENABLED=true
LOG_DIR=logs
```

Опционально `TG_PROXY=socks5://...` — только для Telegram API, не для Max.
