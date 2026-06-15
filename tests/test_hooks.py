"""Tests for app/hooks.py and plugin loading."""

from unittest.mock import AsyncMock, patch

import pytest

from app.hooks import HookEvent, HookRegistry, hooks
from app.max_client import MaxMessage
from app.plugins import load_plugins


@pytest.fixture
def registry():
    reg = HookRegistry()
    yield reg
    reg.clear()


class TestHookRegistry:
    @pytest.mark.asyncio
    async def test_emit_calls_sync_handler(self, registry):
        called = []

        def handler(**kwargs):
            called.append(kwargs.get("value"))

        registry.register("test", handler)
        await registry.emit("test", value=42)
        assert called == [42]

    @pytest.mark.asyncio
    async def test_emit_calls_async_handler(self, registry):
        called = []

        async def handler(**kwargs):
            called.append(kwargs.get("value"))

        registry.register("test", handler)
        await registry.emit("test", value=1)
        assert called == [1]

    @pytest.mark.asyncio
    async def test_on_message_false_blocks(self, registry):
        registry.register(HookEvent.ON_MESSAGE, lambda **kw: False)
        result = await registry.emit(HookEvent.ON_MESSAGE, msg=None)
        assert result is False

    @pytest.mark.asyncio
    async def test_on_message_true_by_default(self, registry):
        registry.register(HookEvent.ON_MESSAGE, lambda **kw: None)
        result = await registry.emit(HookEvent.ON_MESSAGE, msg=None)
        assert result is True

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_stop_chain(self, registry):
        called = []

        def bad(**kwargs):
            raise RuntimeError("boom")

        def good(**kwargs):
            called.append(True)

        registry.register("test", bad)
        registry.register("test", good)
        await registry.emit("test")
        assert called == [True]

    @pytest.mark.asyncio
    async def test_on_tg_reply_ctx_mutation(self, registry):
        async def prefix(**kwargs):
            kwargs["ctx"]["text"] = "prefixed"

        registry.register(HookEvent.ON_TG_REPLY, prefix)
        ctx = {"text": "hello", "cancel": False}
        await registry.emit(HookEvent.ON_TG_REPLY, ctx=ctx)
        assert ctx["text"] == "prefixed"


class TestMessageFilterIntegration:
    @pytest.mark.asyncio
    async def test_hook_filters_message_before_forward(self, registry):
        from app.max_listener import create_max_client

        registry.register(HookEvent.ON_MESSAGE, lambda **kw: False)

        sender = AsyncMock()
        client = create_max_client("t", "d", sender, reply_enabled=False)
        handler = client._on_message_cb

        msg = MaxMessage(chat_id=1, sender_id=2, text="hello", message_id="m1")
        with patch("app.max_listener.hooks", registry):
            await handler(msg)

        sender.send.assert_not_called()


class TestPluginLoading:
    def test_load_plugins_finds_example_logger(self):
        reg = HookRegistry()
        loaded = load_plugins(reg)
        assert "example_logger" in loaded

    def test_plugins_enabled_default_true(self):
        from app.config import Settings

        s = Settings(
            max_token="t",
            max_device_id="d",
            tg_bot_token="b",
            tg_chat_id="1",
        )
        assert s.plugins_enabled is True

    def test_plugins_enabled_false(self):
        from app.config import Settings

        s = Settings(
            max_token="t",
            max_device_id="d",
            tg_bot_token="b",
            tg_chat_id="1",
            plugins_enabled=False,
        )
        assert s.plugins_enabled is False

    def test_global_hooks_singleton(self):
        assert isinstance(hooks, HookRegistry)
