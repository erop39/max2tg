"""Base class for max2tg plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.hooks import HookRegistry


class Plugin:
    """Subclass and override :meth:`register` to attach hook handlers."""

    name: str = "unnamed"

    def register(self, hooks: HookRegistry) -> None:
        raise NotImplementedError
