"""Tests for skip-muted filtering in app/max_listener.py."""

from unittest.mock import AsyncMock

import pytest

from app.max_client import MaxMessage
from app.max_listener import create_max_client


@pytest.fixture
def muted_client():
    sender = AsyncMock()
    client = create_max_client(
        max_token="tok",
        max_device_id="dev",
        sender=sender,
        skip_muted=True,
    )
    return client, sender


class TestSkipMutedListener:
    async def test_muted_chat_message_not_forwarded(self, muted_client):
        client, sender = muted_client
        await client._on_ready_cb({
            "profile": {"id": 1, "names": []},
            "chats": [],
            "settings": {
                "chats": {
                    "100": {"dontDisturbUntil": -1},
                }
            },
        })
        sender.send.reset_mock()

        await client._on_message_cb(
            MaxMessage(chat_id=100, sender_id=2, text="hello")
        )
        sender.send.assert_not_called()

    async def test_unmuted_chat_message_forwarded(self, muted_client):
        client, sender = muted_client
        await client._on_ready_cb({
            "profile": {"id": 1, "names": []},
            "chats": [{"id": 200, "type": "DIALOG", "participants": {"1": {}, "2": {}}}],
            "settings": {"chats": {}},
        })
        sender.send.reset_mock()

        await client._on_message_cb(
            MaxMessage(chat_id=200, sender_id=2, text="hello")
        )
        sender.send.assert_called()

    async def test_skip_muted_disabled_forwards_muted(self):
        sender = AsyncMock()
        client = create_max_client(
            max_token="tok",
            max_device_id="dev",
            sender=sender,
            skip_muted=False,
        )
        await client._on_ready_cb({
            "profile": {"id": 1, "names": []},
            "chats": [{"id": 100, "dontDisturbUntil": -1, "type": "DIALOG", "participants": {}}],
        })
        sender.send.reset_mock()

        await client._on_message_cb(
            MaxMessage(chat_id=100, sender_id=2, text="hello")
        )
        sender.send.assert_called()
