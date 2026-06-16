from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.muted_buffer import MutedMessageBuffer
from app.muted_digest import flush_muted_digest


@pytest.mark.asyncio
async def test_flush_muted_digest_empty_buffer_sends_empty_message():
    sender = SimpleNamespace(send=AsyncMock())
    resolver = SimpleNamespace(chat_name=lambda chat_id: f"chat-{chat_id}")

    total = await flush_muted_digest(
        buffer=MutedMessageBuffer(),
        client=SimpleNamespace(),
        sender=sender,
        resolver=resolver,
    )

    assert total == 0
    sender.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_flush_muted_digest_sorts_within_chat(monkeypatch):
    buffer = MutedMessageBuffer()
    await buffer.add(SimpleNamespace(chat_id=10, timestamp=20, message_id="2"))
    await buffer.add(SimpleNamespace(chat_id=10, timestamp=10, message_id="1"))
    await buffer.add(SimpleNamespace(chat_id=20, timestamp=15, message_id="3"))

    sender = SimpleNamespace(send=AsyncMock())
    resolver = SimpleNamespace(chat_name=lambda chat_id: f"chat-{chat_id}")
    calls = []

    async def fake_forward(msg, client, sender, resolver, reply_enabled=False):
        calls.append((msg.chat_id, msg.message_id))

    monkeypatch.setattr("app.muted_digest.forward_message", fake_forward)

    total = await flush_muted_digest(
        buffer=buffer,
        client=SimpleNamespace(),
        sender=sender,
        resolver=resolver,
    )

    assert total == 3
    assert calls == [(10, "1"), (10, "2"), (20, "3")]
