"""Track per-chat read marks to skip already-read Max messages."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


class ReadTracker:
    """Stores the latest read position (mark) per chat for the account owner."""

    def __init__(self) -> None:
        self._my_id: Any = None
        self._marks: dict[Any, int] = {}

    def set_my_id(self, my_id: Any) -> None:
        self._my_id = my_id

    def load_from_chats(self, chats: list) -> None:
        """Seed read marks from AUTH_SNAPSHOT chat list."""
        for chat in chats:
            if not isinstance(chat, dict):
                continue
            cid = chat.get("id")
            mark = chat.get("mark")
            if cid is not None and mark is not None:
                self._update_mark(cid, int(mark))

    def on_notif_mark(self, payload: dict) -> None:
        """Handle NOTIF_MARK (opcode 130) — read position sync."""
        if self._my_id is None:
            return
        if payload.get("userId") != self._my_id:
            return
        chat_id = payload.get("chatId")
        mark = payload.get("mark")
        if chat_id is not None and mark is not None:
            self._update_mark(chat_id, int(mark))
            log.debug(
                "Read mark: chat=%s mark=%s unread=%s",
                chat_id,
                mark,
                payload.get("unread"),
            )

    def _update_mark(self, chat_id: Any, mark: int) -> None:
        prev = self._marks.get(chat_id, 0)
        if mark > prev:
            self._marks[chat_id] = mark

    def is_unread(self, chat_id: Any, message_time: Any) -> bool:
        """Return True if message_time is newer than the last known read mark."""
        if message_time is None:
            return True
        try:
            msg_ts = int(message_time)
        except (TypeError, ValueError):
            return True
        return msg_ts > self._marks.get(chat_id, 0)
