# Расширения max2tg

Этот форк добавляет слой **хуков** и **плагинов** поверх оригинального [Aist/max2tg](https://github.com/Aist/max2tg). Ядро пересылки не меняется — расширения подключаются через события.

## Быстрый старт

1. Создайте файл `app/plugins/my_plugin.py`
2. Опишите класс, наследующий `Plugin`
3. Перезапустите бота — модуль подхватится автоматически

Отключить все плагины: `PLUGINS_ENABLED=false` в `.env`.

## События (хуки)

| Событие | Когда вызывается | Аргументы |
|---------|------------------|-----------|
| `on_ready` | После успешной авторизации в Max | `snapshot`, `resolver`, `client`, `is_reconnect` |
| `on_message` | До пересылки в Telegram | `msg`, `resolver`, `client` |
| `on_message_sent` | После успешной пересылки | `msg`, `resolver`, `client` |
| `on_disconnect` | При обрыве WebSocket | `client`, `resolver` |
| `on_tg_reply` | Перед отправкой ответа в Max | `ctx`, `update`, `max_client`, `label` |

### Фильтрация сообщений

Обработчик `on_message` может вернуть `False` — сообщение **не** будет переслано в Telegram:

```python
from app.hooks import HookEvent
from app.plugins._base import Plugin

class SpamFilterPlugin(Plugin):
    name = "spam_filter"

    def register(self, hooks):
        hooks.register(HookEvent.ON_MESSAGE, self._on_message)

    async def _on_message(self, msg, **kwargs):
        if "реклама" in (msg.text or "").lower():
            return False
```

### Изменение ответа в Max

В `on_tg_reply` изменяйте словарь `ctx`:

```python
async def _on_tg_reply(self, ctx, **kwargs):
    ctx["text"] = f"[TG] {ctx['text']}"
    # ctx["cancel"] = True  — отменить отправку
```

Поля `ctx`: `text`, `elements`, `max_chat_id`, `cancel`.

## Написание плагина

```python
# app/plugins/my_plugin.py
import logging
from app.hooks import HookEvent
from app.plugins._base import Plugin

log = logging.getLogger(__name__)

class MyPlugin(Plugin):
    name = "my_plugin"

    def register(self, hooks):
        hooks.register(HookEvent.ON_MESSAGE, self._on_message)

    async def _on_message(self, msg, resolver, client, **kwargs):
        log.info("Сообщение из чата %s", msg.chat_id)
```

Альтернатива — функция `register(hooks)` в модуле без класса.

## Пример в комплекте

[`app/plugins/example_logger.py`](app/plugins/example_logger.py) — пишет в лог `chat_id` и `sender_id` каждого входящего сообщения (уровень DEBUG).

## Идеи для своих плагинов

- Фильтр по ключевым словам или списку чатов
- Дублирование важных сообщений во второй Telegram-чат
- Запись истории в SQLite (`on_message_sent`)
- Автоответы или интеграция с LLM (`on_tg_reply`)
- Метрики и алерты при частых `on_disconnect`

## Обновление с upstream

```bash
git remote add upstream https://github.com/Aist/max2tg.git
git fetch upstream
git merge upstream/main
```

После merge проверьте, что вызовы `hooks.emit` в `max_listener.py` / `tg_handler.py` не перезаписаны.
