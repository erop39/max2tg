import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

log = logging.getLogger(__name__)

VALID_TG_FORMAT_STYLES = frozenset({"plain", "enhanced", "compact"})


@dataclass(frozen=True)
class Settings:
    max_token: str
    max_device_id: str
    tg_bot_token: str
    tg_chat_id: str
    max_chat_ids: str | None = None
    tg_proxy: str | None = None
    tg_read_timeout: int | None = None
    tg_write_timeout: int | None = None
    tg_media_write_timeout: int | None = None
    debug: bool = False
    reply_enabled: bool = False
    plugins_enabled: bool = True
    unread_only: bool = False
    unread_delay_sec: float = 2.0
    skip_muted: bool = False
    tg_format_style: str = "enhanced"
    tg_format_separator: bool = True
    tg_format_timestamp: bool = True


def load_settings() -> Settings:
    load_dotenv()

    required = ["MAX_TOKEN", "MAX_DEVICE_ID", "TG_BOT_TOKEN", "TG_CHAT_ID"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise SystemExit(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in the values."
        )

    tg_chat_id = os.environ["TG_CHAT_ID"]
    try:
        int(tg_chat_id)
    except ValueError:
        raise SystemExit(
            f"TG_CHAT_ID must be a valid integer, got: {tg_chat_id!r}"
        )

    raw_format_style = os.environ.get("TG_FORMAT_STYLE", "enhanced").strip().lower()
    if raw_format_style not in VALID_TG_FORMAT_STYLES:
        log.warning(
            "Unknown TG_FORMAT_STYLE=%r, falling back to 'enhanced'",
            raw_format_style,
        )
        raw_format_style = "enhanced"

    return Settings(
        max_token=os.environ["MAX_TOKEN"].strip(),
        max_device_id=os.environ["MAX_DEVICE_ID"].strip(),
        tg_bot_token=os.environ["TG_BOT_TOKEN"].strip(),
        tg_chat_id=os.environ["TG_CHAT_ID"].strip(),
        max_chat_ids=os.environ.get("MAX_CHAT_IDS") or None,
        tg_proxy=os.environ.get("TG_PROXY") or None,
        tg_read_timeout=int(os.environ.get("TG_READ_TIMEOUT", 0)) or None,
        tg_write_timeout=int(os.environ.get("TG_WRITE_TIMEOUT", 0)) or None,
        tg_media_write_timeout=int(os.environ.get("TG_MEDIA_WRITE_TIMEOUT", 0)) or None,
        debug=os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"),
        reply_enabled=os.environ.get("REPLY_ENABLED", "").lower() in ("1", "true", "yes"),
        plugins_enabled=os.environ.get("PLUGINS_ENABLED", "true").lower() not in ("0", "false", "no"),
        unread_only=os.environ.get("UNREAD_ONLY", "").lower() in ("1", "true", "yes"),
        unread_delay_sec=float(os.environ.get("UNREAD_DELAY_SEC", "2") or "2"),
        skip_muted=os.environ.get("SKIP_MUTED", "").lower() in ("1", "true", "yes"),
        tg_format_style=raw_format_style,
        tg_format_separator=os.environ.get("TG_FORMAT_SEPARATOR", "true").lower()
        not in ("0", "false", "no"),
        tg_format_timestamp=os.environ.get("TG_FORMAT_TIMESTAMP", "true").lower()
        not in ("0", "false", "no"),
    )
