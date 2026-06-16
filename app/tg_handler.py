import html
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import telegram.constants

from app.hooks import HookEvent, hooks
from app.max_client import MaxClient
from app.muted_buffer import MutedMessageBuffer
from app.muted_digest import flush_muted_digest
from app.resolver import ContactResolver
from app.tg_sender import TelegramSender

log = logging.getLogger(__name__)

PENDING_REPLY_KEY = "pending_reply_chat_id"
PENDING_REPLY_LABEL_KEY = "pending_reply_label"

_ALLOWED_CHAT_ID_KEY = "allowed_chat_id"
_MUTED_BUFFER_KEY = "muted_buffer"
_MUTED_DIGEST_ENABLED_KEY = "muted_digest_enabled"
_TG_SENDER_KEY = "tg_sender"
_RESOLVER_KEY = "resolver"
_REPLY_ENABLED_KEY = "reply_enabled"


async def _on_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline 'Reply' button press."""
    query = update.callback_query

    allowed_chat_id = context.bot_data.get(_ALLOWED_CHAT_ID_KEY)
    if allowed_chat_id is not None and (
        update.effective_chat.id != allowed_chat_id
        and update.effective_user.id != allowed_chat_id
    ):
        await query.answer()
        return

    await query.answer()

    data = query.data or ""
    if not data.startswith("reply:"):
        return

    chat_id_str = data[len("reply:"):]
    try:
        max_chat_id = int(chat_id_str)
    except ValueError:
        max_chat_id = chat_id_str

    context.user_data[PENDING_REPLY_KEY] = max_chat_id

    source_text = query.message.text or query.message.caption or ""
    label = source_text.split("\n")[0] if source_text else str(max_chat_id)
    context.user_data[PENDING_REPLY_LABEL_KEY] = label
    addressee = ""
    if query.message.chat.type in (telegram.constants.ChatType.GROUP, telegram.constants.ChatType.SUPERGROUP):
        addressee = f" {html.escape(query.from_user.full_name)},"
    await query.message.reply_text(
        f"✏️{addressee} напишите ответ для <b>{html.escape(label)}</b> (ответом на оригинальное сообщение):\n"
        "<i>(или /cancel для отмены)</i>",
        parse_mode="HTML",
    )


async def _on_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel pending reply."""
    if context.user_data.pop(PENDING_REPLY_KEY, None):
        context.user_data.pop(PENDING_REPLY_LABEL_KEY, None)
        await update.message.reply_text("❌ Ответ отменён.")
    else:
        await update.message.reply_text("Нет активного ответа для отмены.")


async def _on_text_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forward user's text as a reply to Max."""
    max_chat_id = context.user_data.pop(PENDING_REPLY_KEY, None)
    label = context.user_data.pop(PENDING_REPLY_LABEL_KEY, None)
    if max_chat_id is None:
        return

    max_client: MaxClient | None = context.bot_data.get("max_client")
    if not max_client:
        await update.message.reply_text("⚠️ Max клиент не подключён.")
        return

    text = update.message.text
    elements = []
    if update.message.chat.type in [telegram.constants.ChatType.GROUP, telegram.constants.ChatType.SUPERGROUP]:
        text = f"💬 {update.message.from_user.full_name}:\n{text}"
        elements = [
            {
                "type": "STRONG",
                "length": len(update.message.from_user.full_name)+1,
                "from": 2
            }
        ]

    ctx = {
        "text": text,
        "elements": elements,
        "max_chat_id": max_chat_id,
        "cancel": False,
    }
    await hooks.emit(
        HookEvent.ON_TG_REPLY,
        ctx=ctx,
        update=update,
        max_client=max_client,
        label=label,
    )
    if ctx.get("cancel"):
        await update.message.reply_text("❌ Ответ отменён плагином.")
        return

    text = ctx["text"]
    elements = ctx["elements"]

    try:
        resp = await max_client.send_message(max_chat_id, text, elements)
        if resp:
            safe_target = html.escape(str(label or max_chat_id))
            await update.message.reply_text(f"✅ Отправлено → <b>{safe_target}</b>", parse_mode="HTML")
        else:
            await update.message.reply_text("⚠️ Не удалось отправить сообщение в Max.")
    except Exception:
        log.exception("Failed to send reply to Max chat %s", max_chat_id)
        await update.message.reply_text("⚠️ Ошибка при отправке в Max.")


async def _on_muted_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.bot_data.get(_MUTED_DIGEST_ENABLED_KEY):
        await update.message.reply_text("Функция чтения заглушённых чатов отключена.")
        return
    buffer: MutedMessageBuffer | None = context.bot_data.get(_MUTED_BUFFER_KEY)
    sender: TelegramSender | None = context.bot_data.get(_TG_SENDER_KEY)
    resolver: ContactResolver | None = context.bot_data.get(_RESOLVER_KEY)
    max_client: MaxClient | None = context.bot_data.get("max_client")
    if not buffer or not sender or not resolver or not max_client:
        await update.message.reply_text("⚠️ Компоненты для чтения заглушённых чатов недоступны.")
        return

    total = await flush_muted_digest(
        buffer=buffer,
        client=max_client,
        sender=sender,
        resolver=resolver,
        reply_enabled=bool(context.bot_data.get(_REPLY_ENABLED_KEY)),
    )
    if total > 0:
        await update.message.reply_text(f"✅ Отправлено сообщений из заглушённых чатов: {total}.")


async def _on_muted_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data != "muted:flush":
        return
    if not context.bot_data.get(_MUTED_DIGEST_ENABLED_KEY):
        await query.message.reply_text("Функция чтения заглушённых чатов отключена.")
        return

    buffer: MutedMessageBuffer | None = context.bot_data.get(_MUTED_BUFFER_KEY)
    sender: TelegramSender | None = context.bot_data.get(_TG_SENDER_KEY)
    resolver: ContactResolver | None = context.bot_data.get(_RESOLVER_KEY)
    max_client: MaxClient | None = context.bot_data.get("max_client")
    if not buffer or not sender or not resolver or not max_client:
        await query.message.reply_text("⚠️ Компоненты для чтения заглушённых чатов недоступны.")
        return

    total = await flush_muted_digest(
        buffer=buffer,
        client=max_client,
        sender=sender,
        resolver=resolver,
        reply_enabled=bool(context.bot_data.get(_REPLY_ENABLED_KEY)),
    )
    if total > 0:
        await query.message.reply_text(f"✅ Отправлено сообщений из заглушённых чатов: {total}.")


def build_tg_app(token: str, max_client: MaxClient, allowed_chat_id: str,
                  proxy_url: str | None = None, read_timeout: int | None = None, write_timeout: int | None = None,
                  muted_buffer: MutedMessageBuffer | None = None, muted_digest_enabled: bool = False,
                  sender: TelegramSender | None = None, resolver: ContactResolver | None = None,
                  reply_enabled: bool = False) -> Application:
    """Build and configure the Telegram Application with handlers."""
    builder = Application.builder().token(token)
    if proxy_url:
        builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)
    if read_timeout:
        builder = builder.read_timeout(read_timeout)
    if write_timeout:
        builder = builder.write_timeout(write_timeout)
    app = builder.build()
    app.bot_data["max_client"] = max_client
    app.bot_data[_ALLOWED_CHAT_ID_KEY] = int(allowed_chat_id)
    app.bot_data[_MUTED_BUFFER_KEY] = muted_buffer
    app.bot_data[_MUTED_DIGEST_ENABLED_KEY] = muted_digest_enabled
    app.bot_data[_TG_SENDER_KEY] = sender
    app.bot_data[_RESOLVER_KEY] = resolver
    app.bot_data[_REPLY_ENABLED_KEY] = reply_enabled

    chat_filter = filters.Chat(chat_id=int(allowed_chat_id))

    app.add_handler(CallbackQueryHandler(_on_reply_button, pattern=r"^reply:"))
    app.add_handler(CallbackQueryHandler(_on_muted_button, pattern=r"^muted:"))
    app.add_handler(CommandHandler("cancel", _on_cancel, filters=chat_filter))
    app.add_handler(CommandHandler("muted", _on_muted_digest, filters=chat_filter))
    app.add_handler(CommandHandler("readmuted", _on_muted_digest, filters=chat_filter))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & chat_filter, _on_text_reply))

    return app
