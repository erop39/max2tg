"""Tests for skip-muted filtering in app/max_listener.py."""

from unittest.mock import AsyncMock

import pytest

from app.max_client import MaxMessage
from app.max_listener import _startup_message, create_max_client


class TestStartupMessage:
    def test_without_muted_count(self):
        assert _startup_message(32) == "✅ <b>Max:</b> подключён | чатов: 32"

    def test_with_muted_count(self):
        text = _startup_message(32, 7)
        assert "чатов: 32" in text
        assert "🔇 из них без звука: 7" in text


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

    async def test_startup_shows_muted_count(self, muted_client):
        client, sender = muted_client
        await client._on_ready_cb({
            "profile": {"id": 1, "names": []},
            "chats": [{"id": 100, "type": "GROUP", "title": "Test", "participants": {}}],
            "settings": {
                "chats": {
                    "100": {"dontDisturbUntil": -1},
                    "200": {"dontDisturbUntil": -1},
                }
            },
        })
        text = sender.send.call_args[0][0]
        assert "чатов: 1" in text
        assert "🔇 из них без звука: 2" in text

    async def test_startup_shows_muted_count(self, muted_client):
        client, sender = muted_client
        await client._on_ready_cb({
            "profile": {"id": 1, "names": []},
            "chats": [{"id": 100, "type": "GROUP", "title": "Test", "participants": {}}],
            "settings": {
                "chats": {
                    "100": {"dontDisturbUntil": -1},
                    "200": {"dontDisturbUntil": -1},
                }
            },
        })
        text = sender.send.call_args[0][0]
        assert "чатов: 1" in text
        assert "🔇 из них без звука: 2" in text
