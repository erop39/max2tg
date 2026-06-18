import asyncio
import concurrent.futures
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import RotatingFileHandler

from telegram import Update

from app.config import load_settings
from app.hooks import hooks
from app.max_listener import create_max_client
from app.muted_buffer import MutedMessageBuffer
from app.plugins import load_plugins
from app.tg_handler import build_tg_app
from app.tg_sender import TelegramSender
from app.version import git_revision

threading.stack_size(524288)

log = logging.getLogger("max2tg")


class _SyncExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor that runs callables synchronously without spawning threads.

    Python 3.12 requires set_default_executor() to receive a ThreadPoolExecutor,
    so we subclass it and override submit() to bypass _adjust_thread_count().
    Used on low-resource servers where the OS cannot create new threads.
    DNS resolution (getaddrinfo) will block the event loop for a few ms,
    which is acceptable for a single-user forwarding bot.
    """

    def submit(self, fn, /, *args, **kwargs):
        f: concurrent.futures.Future = concurrent.futures.Future()
        try:
            f.set_result(fn(*args, **kwargs))
        except Exception as exc:
            f.set_exception(exc)
        return f


async def main():
    loop = asyncio.get_running_loop()
    loop.set_default_executor(_SyncExecutor())

    settings = load_settings()

    level = logging.DEBUG if settings.debug else logging.INFO
    fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    log_dir = os.environ.get("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "max2tg.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    logging.basicConfig(level=level, handlers=[console_handler, file_handler], force=True)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING if not settings.debug else logging.DEBUG)

    log.info("Debug mode: %s", "ON" if settings.debug else "OFF")
    log.info("max2tg version: %s", git_revision())

    if settings.plugins_enabled:
        loaded = load_plugins(hooks)
        log.info("Plugins enabled: %s", ", ".join(loaded) if loaded else "(none)")
    else:
        log.info("Plugins disabled (PLUGINS_ENABLED=false)")

    if settings.tg_proxy:
        log.info("Using Telegram proxy: %s", settings.tg_proxy.split("@")[-1])

    sender = TelegramSender(
        settings.tg_bot_token,
        settings.tg_chat_id,
        proxy_url=settings.tg_proxy,
        read_timeout=settings.tg_read_timeout,
        write_timeout=settings.tg_write_timeout,
        media_write_timeout=settings.tg_media_write_timeout,
    )
    await sender.start()
    muted_buffer = MutedMessageBuffer() if settings.muted_digest_enabled else None
    skip_muted_enabled = settings.skip_muted or settings.muted_digest_enabled

    client = create_max_client(
        settings.max_token, settings.max_device_id, sender, settings.max_chat_ids,
        debug=settings.debug, reply_enabled=settings.reply_enabled,
        unread_only=settings.unread_only, unread_delay_sec=settings.unread_delay_sec,
        skip_muted=skip_muted_enabled,
        muted_digest_enabled=settings.muted_digest_enabled,
        muted_buffer=muted_buffer,
    )

    if settings.unread_only:
        log.info(
            "Unread-only mode: ON (delay %ss before forward check)",
            settings.unread_delay_sec,
        )
    if skip_muted_enabled:
        log.info("Skip-muted mode: ON (no forwards from muted Max chats)")
    if settings.muted_digest_enabled:
        log.info("Muted digest mode: ON (/muted command enabled)")

    tg_app = None
    if settings.reply_enabled or settings.muted_digest_enabled:
        tg_app = build_tg_app(settings.tg_bot_token, client, settings.tg_chat_id,
                              proxy_url=settings.tg_proxy, read_timeout=settings.tg_read_timeout, write_timeout=settings.tg_write_timeout,
                              muted_buffer=muted_buffer, muted_digest_enabled=settings.muted_digest_enabled,
                              sender=sender, resolver=client.resolver, reply_enabled=settings.reply_enabled)
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
        log.info("Telegram polling started")
    else:
        log.info("Telegram polling disabled (REPLY_ENABLED=false and MUTED_DIGEST_ENABLED=false)")

    log.info("Starting Max listener...")
    try:
        await client.run()
    finally:
        log.info("Shutting down...")
        if tg_app:
            await tg_app.updater.stop()
            await tg_app.stop()
            await tg_app.shutdown()
        await sender.stop()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        log.info("Stopped.")
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()
