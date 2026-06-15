"""Event hooks for extending max2tg without modifying core logic."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger(__name__)

HookHandler = Callable[..., bool | None | Awaitable[bool | None]]


class HookEvent:
    ON_READY = "on_ready"
    ON_MESSAGE = "on_message"
    ON_MESSAGE_SENT = "on_message_sent"
    ON_DISCONNECT = "on_disconnect"
    ON_TG_REPLY = "on_tg_reply"


class HookRegistry:
    """Registry of async/sync handlers keyed by event name."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[HookHandler]] = {}

    def register(self, event: str, handler: HookHandler) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def clear(self) -> None:
        self._handlers.clear()

    async def emit(self, event: str, **kwargs: Any) -> bool:
        """Run handlers for *event*.

        For ``ON_MESSAGE``: returns ``False`` if any handler returns ``False``
        (message will not be forwarded). For other events the return value is
        always ``True``; handlers may mutate objects passed in *kwargs* (e.g.
        ``ctx`` for ``ON_TG_REPLY``).
        """
        for handler in self._handlers.get(event, []):
            try:
                result = handler(**kwargs)
                if inspect.isawaitable(result):
                    result = await result
                if event == HookEvent.ON_MESSAGE and result is False:
                    return False
            except Exception:
                log.exception("Hook handler failed for event %s", event)
        return True


hooks = HookRegistry()
