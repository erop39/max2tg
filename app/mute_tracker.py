"""Track muted (do-not-disturb) Max chats."""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)


def _normalize_chat_id(chat_id: Any) -> Any:
    try:
        return int(chat_id)
    except (TypeError, ValueError):
        return chat_id


def _extract_dont_disturb_until(chat: dict) -> int | None:
    """Read mute deadline from a chat or settings object."""
    if not isinstance(chat, dict):
        return None
    for key in ("dontDisturbUntil", "dont_disturb_until"):
        if key in chat:
            return chat[key]
    settings = chat.get("settings")
    if isinstance(settings, dict):
        for key in ("dontDisturbUntil", "dont_disturb_until"):
            if key in settings:
                return settings[key]
    return None


class MuteTracker:
    """Tracks chats with notifications muted in Max."""

    def __init__(self) -> None:
        self._permanent: set[Any] = set()
        self._until: dict[Any, int] = {}

    def load_from_chats(self, chats: list) -> None:
        for chat in chats:
            if isinstance(chat, dict) and chat.get("id") is not None:
                self.update_chat(chat)

    def load_from_snapshot(self, snapshot: dict) -> None:
        """Load mute state from AUTH_SNAPSHOT (chats list + settings.chats map)."""
        self.load_from_chats(snapshot.get("chats", []))
        self.on_settings(snapshot)
        log.info(
            "Mute state loaded from snapshot: %d muted chat(s)",
            len(self._permanent),
        )

    def update_from_payload(self, payload: dict) -> None:
        """Apply mute updates from NOTIF_CHAT / NOTIF_CONFIG payloads."""
        if not isinstance(payload, dict):
            return
        chat = payload.get("chat")
        if isinstance(chat, dict):
            self.update_chat(chat)
            return
        if payload.get("id") is not None or payload.get("chatId") is not None:
            self.update_chat(payload)
            return
        if payload.get("settings") is not None or payload.get("chats") is not None:
            self.on_settings(payload)

    def update_chat(self, chat: dict) -> None:
        chat_id = _normalize_chat_id(chat.get("id") or chat.get("chatId"))
        if chat_id is None:
            return
        ddu = _extract_dont_disturb_until(chat)
        if ddu is not None:
            self._apply(chat_id, int(ddu))

    def on_settings(self, payload: dict) -> None:
        """Handle CONFIG / NOTIF_CONFIG payloads with nested chat settings."""
        settings = payload.get("settings") or payload
        chats = settings.get("chats")
        if not isinstance(chats, dict):
            return
        for chat_id, chat_settings in chats.items():
            cid = _normalize_chat_id(chat_id)
            if isinstance(chat_settings, dict):
                ddu = _extract_dont_disturb_until(chat_settings)
            else:
                ddu = chat_settings
            if ddu is not None:
                self._apply(cid, int(ddu))

    def _apply(self, chat_id: Any, dont_disturb_until: int) -> None:
        if dont_disturb_until == 0:
            self._permanent.discard(chat_id)
            self._until.pop(chat_id, None)
            log.info("Chat unmuted: %s", chat_id)
            return

        if dont_disturb_until == -1:
            self._permanent.add(chat_id)
            self._until.pop(chat_id, None)
            log.info("Chat muted permanently: %s", chat_id)
            return

        now_ms = int(time.time() * 1000)
        if dont_disturb_until > now_ms:
            self._permanent.add(chat_id)
            self._until[chat_id] = dont_disturb_until
            log.info("Chat muted until %s: %s", dont_disturb_until, chat_id)
        else:
            self._permanent.discard(chat_id)
            self._until.pop(chat_id, None)

    def is_muted(self, chat_id: Any) -> bool:
        cid = _normalize_chat_id(chat_id)
        if cid not in self._permanent:
            return False
        until = self._until.get(cid)
        if until is None:
            return True
        now_ms = int(time.time() * 1000)
        if now_ms >= until:
            self._permanent.discard(cid)
            self._until.pop(cid, None)
            return False
        return True
