"""In-memory buffer for messages from muted Max chats."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.max_client import MaxMessage


class MutedMessageBuffer:
    """Stores muted-chat messages grouped by chat preserving first-seen chat order."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._chat_order: list[Any] = []
        self._messages: dict[Any, list[MaxMessage]] = {}

    async def add(self, msg: MaxMessage) -> None:
        chat_id = msg.chat_id
        async with self._lock:
            bucket = self._messages.get(chat_id)
            if bucket is None:
                self._chat_order.append(chat_id)
                self._messages[chat_id] = [msg]
                return
            bucket.append(msg)

    async def get_grouped(self) -> list[tuple[Any, list[MaxMessage]]]:
        async with self._lock:
            grouped: list[tuple[Any, list[MaxMessage]]] = []
            for chat_id in self._chat_order:
                messages = self._messages.get(chat_id)
                if messages:
                    grouped.append((chat_id, list(messages)))
            return grouped

    async def pop_grouped(self) -> list[tuple[Any, list[MaxMessage]]]:
        async with self._lock:
            grouped: list[tuple[Any, list[MaxMessage]]] = []
            for chat_id in self._chat_order:
                messages = self._messages.get(chat_id)
                if messages:
                    grouped.append((chat_id, list(messages)))
            self._chat_order.clear()
            self._messages.clear()
            return grouped

    async def clear(self) -> None:
        async with self._lock:
            self._chat_order.clear()
            self._messages.clear()

    async def count(self) -> int:
        async with self._lock:
            return sum(len(messages) for messages in self._messages.values())

    async def prune_read(self, chat_id: Any, read_mark: int) -> None:
        async with self._lock:
            messages = self._messages.get(chat_id)
            if not messages:
                return
            pruned = [msg for msg in messages if not _is_read(msg, read_mark)]
            if pruned:
                self._messages[chat_id] = pruned
                return
            self._messages.pop(chat_id, None)
            self._chat_order = [cid for cid in self._chat_order if cid != chat_id]

    async def prune_many(self, read_marks: Iterable[tuple[Any, int]]) -> None:
        for chat_id, read_mark in read_marks:
            await self.prune_read(chat_id, read_mark)


def _is_read(msg: MaxMessage, read_mark: int) -> bool:
    if msg.timestamp is None:
        return False
    try:
        return int(msg.timestamp) <= int(read_mark)
    except (TypeError, ValueError):
        return False
