"""Helpers to flush buffered messages from muted chats."""

from __future__ import annotations

from html import escape

from app.max_client import MaxClient
from app.max_listener import forward_message
from app.muted_buffer import MutedMessageBuffer
from app.resolver import ContactResolver
from app.tg_sender import TelegramSender


def _msg_sort_key(msg) -> tuple[int, str]:
    ts = msg.timestamp
    try:
        ts_val = int(ts)
    except (TypeError, ValueError):
        ts_val = 0
    return ts_val, msg.message_id


async def flush_muted_digest(
    buffer: MutedMessageBuffer,
    client: MaxClient,
    sender: TelegramSender,
    resolver: ContactResolver,
    reply_enabled: bool = False,
) -> int:
    grouped = await buffer.pop_grouped()
    if not grouped:
        await sender.send("📭 Нет новых сообщений из заглушённых чатов.")
        return 0

    # Resolve unknown senders so group messages show names, not numeric IDs.
    sender_ids = {
        msg.sender_id
        for _, messages in grouped
        for msg in messages
        if getattr(msg, "sender_id", None) is not None
    }
    if sender_ids:
        await resolver.resolve_users_batch(list(sender_ids))

    total = 0
    for chat_id, messages in grouped:
        messages_sorted = sorted(messages, key=_msg_sort_key)
        chat_label = escape(resolver.chat_name(chat_id))
        if chat_label.startswith("DM:"):
            try:
                peer_id = int(chat_label[3:])
                chat_label = escape(await resolver.resolve_user(peer_id))
            except ValueError:
                pass
        await sender.send(f"🔇 <b>{chat_label}</b> ({len(messages_sorted)} сообщений)")
        for msg in messages_sorted:
            await forward_message(msg, client, sender, resolver, reply_enabled=reply_enabled)
            total += 1
    return total
