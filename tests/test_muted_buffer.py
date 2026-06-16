from types import SimpleNamespace

import pytest

from app.muted_buffer import MutedMessageBuffer


@pytest.mark.asyncio
async def test_add_and_get_grouped_preserves_chat_order():
    buffer = MutedMessageBuffer()
    await buffer.add(SimpleNamespace(chat_id=2, timestamp=20, message_id="m2"))
    await buffer.add(SimpleNamespace(chat_id=1, timestamp=10, message_id="m1"))
    await buffer.add(SimpleNamespace(chat_id=2, timestamp=30, message_id="m3"))

    grouped = await buffer.get_grouped()
    assert [chat_id for chat_id, _ in grouped] == [2, 1]
    assert [m.message_id for m in grouped[0][1]] == ["m2", "m3"]


@pytest.mark.asyncio
async def test_prune_read_removes_read_messages_and_chat_bucket():
    buffer = MutedMessageBuffer()
    await buffer.add(SimpleNamespace(chat_id=5, timestamp=100, message_id="a"))
    await buffer.add(SimpleNamespace(chat_id=5, timestamp=200, message_id="b"))

    await buffer.prune_read(5, 150)
    grouped = await buffer.get_grouped()
    assert len(grouped) == 1
    assert [m.message_id for m in grouped[0][1]] == ["b"]

    await buffer.prune_read(5, 999)
    grouped = await buffer.get_grouped()
    assert grouped == []


@pytest.mark.asyncio
async def test_pop_grouped_clears_buffer():
    buffer = MutedMessageBuffer()
    await buffer.add(SimpleNamespace(chat_id=7, timestamp=1, message_id="m"))

    grouped = await buffer.pop_grouped()
    assert len(grouped) == 1
    assert await buffer.count() == 0
