import asyncio
import logging
from datetime import datetime
from html import escape
from typing import Any

from app.hooks import HookEvent, hooks
from app.max_client import MaxClient, MaxMessage, OpCode
from app.resolver import ContactResolver
from app.tg_sender import TelegramSender, reply_keyboard

log = logging.getLogger(__name__)

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
SEPARATOR_LINE = "━━━━━━━━━━━━━━━━"


def _format_time(timestamp: Any) -> str:
    if timestamp is None:
        return ""
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return ""
    if ts > 1_000_000_000_000:
        ts //= 1000
    try:
        return datetime.fromtimestamp(ts).strftime("%H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def _needs_separator(
    last_key: tuple | None,
    chat_id: Any,
    sender_id: Any,
    separator_enabled: bool,
) -> bool:
    if not separator_enabled or last_key is None:
        return False
    return last_key != (chat_id, sender_id)


def _header_plain(sender_label: str, chat_label: str, is_dm: bool) -> str:
    if is_dm:
        return f"✉ <b>{sender_label}</b>"
    if chat_label:
        return f"💬 <b>{chat_label}</b> | {sender_label}"
    return f"💬 <b>{sender_label}</b>"


def _build_header(
    sender_label: str,
    chat_label: str,
    is_dm: bool,
    style: str,
    timestamp: Any,
    show_timestamp: bool,
) -> str:
    if style == "plain":
        return _header_plain(sender_label, chat_label, is_dm)

    time_suffix = ""
    if show_timestamp:
        time_str = _format_time(timestamp)
        if time_str:
            time_suffix = f" · {time_str}"

    if is_dm:
        return f"✉ <b>{sender_label}</b>{time_suffix}"
    if chat_label:
        return f"💬 <b>{chat_label}</b>\n👤 <b>{sender_label}</b>{time_suffix}"
    return f"💬 <b>{sender_label}</b>{time_suffix}"


def _format_body_text(text: str, style: str, *, use_blockquote: bool = True) -> str:
    if not text:
        return ""
    escaped = escape(text)
    if style == "plain" or not use_blockquote:
        return escaped
    return f"<blockquote>{escaped}</blockquote>"


def _join_header_body(header: str, body: str, *, gap: str = "\n\n") -> str:
    if header and body:
        return f"{header}{gap}{body}"
    return header or body


class MessageFormatter:
    def __init__(
        self,
        style: str = "enhanced",
        separator_enabled: bool = True,
        show_timestamp: bool = True,
    ) -> None:
        self.style = style
        self.separator_enabled = separator_enabled
        self.show_timestamp = show_timestamp
        self.last_sender_key: tuple | None = None

    def begin_message(
        self,
        chat_id: Any,
        sender_id: Any,
        sender_label: str,
        chat_label: str,
        is_dm: bool,
        timestamp: Any,
    ) -> str:
        sender_key = (chat_id, sender_id)
        same_sender = self.last_sender_key == sender_key
        need_sep = _needs_separator(
            self.last_sender_key,
            chat_id,
            sender_id,
            self.separator_enabled and self.style != "plain",
        )
        self.last_sender_key = sender_key

        parts: list[str] = []
        if need_sep:
            parts.append(SEPARATOR_LINE)

        show_header = self.style == "plain" or self.style == "enhanced" or not same_sender
        if show_header:
            header_style = "enhanced" if self.style == "compact" else self.style
            parts.append(
                _build_header(
                    sender_label,
                    chat_label,
                    is_dm,
                    header_style,
                    timestamp,
                    self.show_timestamp,
                )
            )

        if self.style == "plain":
            return "\n".join(parts)
        return "\n\n".join(parts)

    def format_content(self, text: str, *, use_blockquote: bool = True) -> str:
        return _format_body_text(text, self.style, use_blockquote=use_blockquote)

    def join_header_body(self, header: str, body: str) -> str:
        gap = "\n" if self.style == "plain" else "\n\n"
        return _join_header_body(header, body, gap=gap)

    def format_text_message(
        self,
        chat_id: Any,
        sender_id: Any,
        sender_label: str,
        chat_label: str,
        is_dm: bool,
        text: str,
        timestamp: Any,
    ) -> str:
        header = self.begin_message(
            chat_id, sender_id, sender_label, chat_label, is_dm, timestamp
        )
        return self.join_header_body(header, self.format_content(text))


def _header(msg: MaxMessage, sender_label: str, chat_label: str, is_dm: bool) -> str:
    return _header_plain(sender_label, chat_label, is_dm)


def _extract_photo_url(attach: dict) -> str | None:
    """Extract the best available URL for a PHOTO attachment."""
    return attach.get("baseUrl") or attach.get("url")


def _extract_file_url(attach: dict) -> str | None:
    """Extract download URL for a FILE attachment (url field takes priority)."""
    url = attach.get("url")
    if url and url.startswith("http"):
        return url
    return None


def _guess_media_kind(filename: str) -> str:
    name_lower = filename.lower()
    for ext in PHOTO_EXTENSIONS:
        if name_lower.endswith(ext):
            return "photo"
    for ext in VIDEO_EXTENSIONS:
        if name_lower.endswith(ext):
            return "video"
    return "document"


async def _send_attach(
    attach: dict,
    client: MaxClient,
    sender: TelegramSender,
    header_text: str,
    chat_id: Any,
    message_id: Any,
    kb=None,
) -> bool:
    """Process and send a single attachment. Returns True if handled."""
    atype = attach.get("_type", "")
    log.info("Processing attach _type=%s keys=%s", atype, list(attach.keys()))

    if atype == "CONTROL" or atype == "WIDGET" or atype == "INLINE_KEYBOARD":
        return False

    if atype == "PHOTO":
        url = _extract_photo_url(attach)
        if not url:
            log.warning("PHOTO attach has no URL: %s", attach)
            return False
        data = await client.download_file(url)
        if data:
            await sender.send_photo(data, caption=header_text, reply_markup=kb)
            return True
        await sender.send(f"{header_text}\n<i>[фото — не удалось загрузить]</i>", reply_markup=kb)
        return True

    if atype == "VIDEO":
        thumb = attach.get("thumbnail")
        if thumb:
            data = await client.download_file(thumb)
            if data:
                await sender.send_photo(data, caption=f"{header_text}\n<i>[видео — превью]</i>", reply_markup=kb)
                return True
        await sender.send(f"{header_text}\n<i>[видео]</i>", reply_markup=kb)
        return True

    if atype == "FILE":
        name = attach.get("name", "file")
        size = attach.get("size", 0)
        token_url = _extract_file_url(attach)
        file_id = attach.get("fileId")
        if not token_url and file_id and chat_id and message_id:
            log.info("Get url by fileId chatId=%s fileId=%s messageId=%s", chat_id, file_id, message_id)
            resp = await client.cmd(
                OpCode.GET_FILE_URL,
                {
                    "chatId": chat_id,
                    "fileId": file_id,
                    "messageId": message_id,
                },
            )
            token_url = resp.get("url")
            log.info("Got url by fileId: %s", token_url)
        if token_url:
            data = await client.download_file(token_url)
            if data:
                kind = _guess_media_kind(name)
                if kind == "photo":
                    await sender.send_photo(data, caption=header_text, filename=name, reply_markup=kb)
                elif kind == "video":
                    await sender.send_video(data, caption=header_text, filename=name, reply_markup=kb)
                else:
                    await sender.send_document(data, caption=header_text, filename=name, reply_markup=kb)
                return True
        size_str = f" ({_human_size(size)})" if size else ""
        await sender.send(f"{header_text}\n📎 <b>{escape(name)}</b>{size_str}", reply_markup=kb)
        return True

    if atype == "AUDIO":
        url = attach.get("url")
        if url:
            data = await client.download_file(url)
            if data:
                await sender.send_voice(data, caption=header_text, reply_markup=kb)
                return True
        await sender.send(f"{header_text}\n<i>[аудио]</i>", reply_markup=kb)
        return True

    if atype == "STICKER":
        url = attach.get("url")
        if url:
            data = await client.download_file(url)
            if data:
                await sender.send_sticker(data, reply_markup=kb)
                return True
        await sender.send(f"{header_text}\n<i>[стикер]</i>", reply_markup=kb)
        return True

    if atype == "SHARE":
        share_url = attach.get("url", "")
        title = attach.get("title", "")
        desc = attach.get("description", "")
        parts = [header_text]
        if title:
            parts.append(f"🔗 <b>{escape(title)}</b>")
        if share_url:
            parts.append(escape(share_url))
        if desc:
            parts.append(f"<i>{escape(desc[:200])}</i>")
        await sender.send("\n".join(parts), reply_markup=kb)
        return True

    if atype == "LOCATION":
        lat = attach.get("lat") or attach.get("latitude")
        lon = attach.get("lon") or attach.get("lng") or attach.get("longitude")
        if lat and lon:
            await sender.send(f"{header_text}\n📍 {lat}, {lon}", reply_markup=kb)
        else:
            await sender.send(f"{header_text}\n<i>[геолокация]</i>", reply_markup=kb)
        return True

    if atype == "CONTACT":
        name = attach.get("name", "")
        phone = attach.get("phone", "")
        text = f"{header_text}\n👤 {escape(name)}"
        if phone:
            text += f" — {escape(phone)}"
        await sender.send(text, reply_markup=kb)
        return True

    log.info("Unknown attach type %s, sending as info", atype)
    await sender.send(f"{header_text}\n<i>[вложение: {escape(atype or 'unknown')}]</i>", reply_markup=kb)
    return True


async def _handle_forward_message(
    link: dict,
    header_text: str,
    client: MaxClient,
    sender: TelegramSender,
    resolver: ContactResolver,
    kb=None,
    formatter: MessageFormatter | None = None,
) -> None:
    """Handle FORWARD link inside a message."""
    fwd_meaningful, fwd_sender_label, fwd_text = await _parse_link(link, resolver)

    prefix = "↩️ <b>Переслано</b>"
    if fwd_sender_label:
        prefix = f"↩️ <b>Переслано от {fwd_sender_label}</b>"

    full_header = f"{header_text}\n{prefix}" if header_text else prefix
    join = formatter.join_header_body if formatter else lambda h, b: _join_header_body(h, b, gap="\n")
    if fwd_meaningful:
        text_sent = False
        for i, attach in enumerate(fwd_meaningful):
            if i == 0 and fwd_text:
                body = formatter.format_content(fwd_text) if formatter else escape(fwd_text)
                cap = join(full_header, body)
                text_sent = True
            else:
                cap = full_header
            await _send_attach(attach, client, sender, cap, None, None, kb=kb)

        if fwd_text and not text_sent:
            body = formatter.format_content(fwd_text) if formatter else escape(fwd_text)
            await sender.send(join(full_header, body), reply_markup=kb)
    elif fwd_text:
        body = formatter.format_content(fwd_text) if formatter else escape(fwd_text)
        await sender.send(join(full_header, body), reply_markup=kb)
    else:
        await sender.send(f"{full_header}\n<i>[без содержимого]</i>", reply_markup=kb)


async def _handle_reply_message(
    link: dict,
    header_text: str,
    resolver: ContactResolver,
):
    fwd_meaningful, fwd_sender_label, fwd_text = await _parse_link(link, resolver)

    prefix = "↩ <b>Ответ</b>"
    if fwd_sender_label:
        prefix = f"↩ <b>Ответ на {fwd_sender_label}</b>"

    full_header = f"{header_text}\n{prefix}" if header_text else prefix
    attaches_str = ""
    if fwd_meaningful:
        for fwd_attach in fwd_meaningful:
            name = fwd_attach.get("name", "file")
            size = fwd_attach.get("size", 0)
            size_str = f" ({_human_size(size)})" if size else ""
            attaches_str += f"📎 <b>{escape(name)}</b>{size_str}\n"
    return attaches_str, full_header, fwd_text


async def _parse_link(link: dict, resolver: ContactResolver):
    inner = link.get("message") or link
    fwd_sender_id = inner.get("sender") or link.get("sender")
    fwd_text = inner.get("text", "") or link.get("text", "")
    fwd_attaches = inner.get("attaches") or link.get("attaches") or []
    fwd_sender_label = ""
    if fwd_sender_id:
        fwd_sender_label = escape(await resolver.resolve_user(fwd_sender_id))
    fwd_meaningful = [
        a for a in fwd_attaches
        if isinstance(a, dict) and a.get("_type") not in ("CONTROL", "WIDGET", "INLINE_KEYBOARD", None)
    ]
    return fwd_meaningful, fwd_sender_label, fwd_text

def _human_size(n: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ТБ"


def create_max_client(
    max_token: str, max_device_id: str, sender: TelegramSender, max_chat_ids: str | None = None,
    debug: bool = False, reply_enabled: bool = False,
    unread_only: bool = False, unread_delay_sec: float = 2.0, skip_muted: bool = False,
    tg_format_style: str = "enhanced",
    tg_format_separator: bool = True,
    tg_format_timestamp: bool = True,
) -> MaxClient:
    client = MaxClient(
        token=max_token, device_id=max_device_id, debug=debug, chat_ids=max_chat_ids,
        unread_only=unread_only, skip_muted=skip_muted,
    )
    resolver = ContactResolver(client=client)
    formatter = MessageFormatter(
        style=tg_format_style,
        separator_enabled=tg_format_separator,
        show_timestamp=tg_format_timestamp,
    )

    _first_connect = True
    _notif_count = 0
    _last_notif_time: datetime | None = None

    def _can_notify() -> bool:
        if _last_notif_time is None:
            return True
        elapsed = (datetime.now() - _last_notif_time).total_seconds()
        if _notif_count == 1:
            return elapsed >= 3600    # 2-е: через 1 час
        if _notif_count == 2:
            return elapsed >= 10800   # 3-е: через 3 часа
        return elapsed >= 86400       # 4-е и далее: раз в сутки

    @client.on_ready
    async def handle_ready(snapshot: dict):
        nonlocal _first_connect
        participant_ids = resolver.load_snapshot(snapshot)

        if client.read_tracker:
            client.read_tracker.set_my_id(resolver._my_id)
            client.read_tracker.load_from_chats(snapshot.get("chats", []))
            log.info("Unread-only mode: read marks loaded from snapshot")

        if client.mute_tracker:
            client.mute_tracker.load_from_chats(snapshot.get("chats", []))
            log.info("Skip-muted mode: mute state loaded from snapshot")

        if participant_ids:
            log.info("Batch-resolving %d participants...", len(participant_ids))
            await resolver.resolve_users_batch(participant_ids)
            log.info("Resolved users: %s", resolver.users)

            log.info("Known chats: %s", resolver.chats)
            log.info("Known users: %s", resolver.users)

        await hooks.emit(
            HookEvent.ON_READY,
            snapshot=snapshot,
            resolver=resolver,
            client=client,
            is_reconnect=not _first_connect,
        )

        if not _first_connect:
            await sender.send("✅ <b>Max:</b> соединение восстановлено")
        else:
            chat_count = len(resolver.chats)
            await sender.send(f"✅ <b>Max:</b> подключён | чатов: {chat_count}")
        _first_connect = False

    @client.on_disconnect
    async def handle_disconnect():
        nonlocal _notif_count, _last_notif_time
        await hooks.emit(HookEvent.ON_DISCONNECT, client=client, resolver=resolver)
        if not _can_notify():
            log.info("Disconnect notification suppressed (throttle)")
            return
        _notif_count += 1
        _last_notif_time = datetime.now()
        await sender.send("⚠️ <b>Max:</b> соединение потеряно, переподключение...")

    @client.on_message
    async def handle_message(msg: MaxMessage):
        log.info(
            "New message: chat=%s sender=%s is_self=%s text=%r attaches=%d",
            msg.chat_id,
            msg.sender_id,
            msg.is_self,
            (msg.text[:80] + "…") if len(msg.text) > 80 else msg.text,
            len(msg.attaches),
        )

        if msg.is_self:
            return

        if not await hooks.emit(
            HookEvent.ON_MESSAGE, msg=msg, resolver=resolver, client=client
        ):
            log.info("Message filtered by hook (chat=%s)", msg.chat_id)
            return

        if client.skip_muted and client.mute_tracker and client.mute_tracker.is_muted(msg.chat_id):
            log.info("Skipped (muted chat in Max): chat=%s", msg.chat_id)
            return

        if client.unread_only and client.read_tracker:
            if unread_delay_sec > 0:
                await asyncio.sleep(unread_delay_sec)
            if not client.read_tracker.is_unread(msg.chat_id, msg.timestamp):
                log.info(
                    "Skipped (already read in Max): chat=%s msg=%s",
                    msg.chat_id,
                    msg.message_id,
                )
                return

        async def _message_sent() -> None:
            await hooks.emit(
                HookEvent.ON_MESSAGE_SENT, msg=msg, resolver=resolver, client=client
            )

        sender_label = escape(await resolver.resolve_user(msg.sender_id))
        is_dm = resolver.is_dm(msg.chat_id)
        if len(client.chat_ids) == 1:
            chat_label = ""
        else:
            chat_label = escape(resolver.chat_name(msg.chat_id))
        header_text = formatter.begin_message(
            msg.chat_id, msg.sender_id, sender_label, chat_label, is_dm, msg.timestamp
        )
        kb = reply_keyboard(msg.chat_id) if reply_enabled else None

        link = msg.link
        link_type = link.get("type") if isinstance(link, dict) else None

        if link_type == "FORWARD":
            await _handle_forward_message(link, header_text, client, sender, resolver, kb=kb, formatter=formatter)
            if msg.text:
                await sender.send(
                    formatter.join_header_body(header_text, formatter.format_content(msg.text)),
                    reply_markup=kb,
                )
            log.info("Forwarded message → TG")
            await _message_sent()
            return

        if link_type == "REPLY":
            attaches_str, full_header, fwd_text = await _handle_reply_message(link, header_text, resolver)
            if msg.text:
                reply_body = formatter.format_content(msg.text, use_blockquote=False)
                await sender.send(
                    f"{full_header}\n<blockquote>{escape(fwd_text)}{attaches_str}</blockquote>{reply_body}",
                    reply_markup=kb,
                )
            log.info("Forwarded reply → TG")
            await _message_sent()
            return

        meaningful_attaches = [
            a for a in msg.attaches
            if isinstance(a, dict) and a.get("_type") not in ("CONTROL", "WIDGET", "INLINE_KEYBOARD", None)
        ]

        if meaningful_attaches:
            text_sent = False
            for i, attach in enumerate(meaningful_attaches):
                if i == 0 and msg.text:
                    cap = formatter.join_header_body(header_text, formatter.format_content(msg.text))
                    text_sent = True
                else:
                    cap = header_text
                await _send_attach(attach, client, sender, cap, msg.chat_id, msg.message_id, kb=kb)
                log.info("Forwarded attach _type=%s → TG", attach.get("_type"))

            if msg.text and not text_sent:
                await sender.send(
                    formatter.join_header_body(header_text, formatter.format_content(msg.text)),
                    reply_markup=kb,
                )
            await _message_sent()
        else:
            if msg.text:
                await sender.send(
                    formatter.join_header_body(header_text, formatter.format_content(msg.text)),
                    reply_markup=kb,
                )
                log.info("Forwarded text → TG")
                await _message_sent()
            else:
                log.warning("Нетекстовое сообщение! %s", msg.attaches)

    return client
