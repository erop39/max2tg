"""Example plugin: logs each incoming Max message chat_id and sender."""

from __future__ import annotations

import logging

from app.hooks import HookEvent
from app.plugins._base import Plugin

log = logging.getLogger(__name__)


class ExampleLoggerPlugin(Plugin):
    name = "example_logger"

    def register(self, hooks) -> None:
        hooks.register(HookEvent.ON_MESSAGE, self._on_message)
        hooks.register(HookEvent.ON_MESSAGE_SENT, self._on_message_sent)
        log.info("Plugin %s registered", self.name)

    async def _on_message(self, msg, resolver, client, **kwargs) -> None:
        log.debug(
            "Plugin %s: incoming message chat=%s sender=%s text_len=%d",
            self.name,
            msg.chat_id,
            msg.sender_id,
            len(msg.text or ""),
        )

    async def _on_message_sent(self, msg, resolver, client, **kwargs) -> None:
        log.debug(
            "Plugin %s: forwarded message chat=%s id=%s",
            self.name,
            msg.chat_id,
            msg.message_id,
        )
