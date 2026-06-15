"""Auto-discovery and loading of max2tg plugins."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

from app.plugins import _base

if TYPE_CHECKING:
    from app.hooks import HookRegistry

log = logging.getLogger(__name__)

_SKIP_MODULES = frozenset({"_base", "__init__"})


def _iter_plugin_modules():
    package = importlib.import_module("app.plugins")
    for info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        module_name = info.name.rsplit(".", 1)[-1]
        if module_name in _SKIP_MODULES or module_name.startswith("_"):
            continue
        yield info.name


def _instantiate_plugin(module) -> _base.Plugin | None:
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if (
            isinstance(obj, type)
            and issubclass(obj, _base.Plugin)
            and obj is not _base.Plugin
        ):
            return obj()
    register = getattr(module, "register", None)
    if callable(register):
        return _FunctionPlugin(register, getattr(module, "__name__", "anonymous"))
    return None


class _FunctionPlugin(_base.Plugin):
    def __init__(self, register_fn, name: str) -> None:
        self.name = name
        self._register_fn = register_fn

    def register(self, hooks: HookRegistry) -> None:
        self._register_fn(hooks)


def load_plugins(hooks: HookRegistry) -> list[str]:
    """Import all plugin modules under ``app.plugins`` and call ``register``."""
    loaded: list[str] = []
    for module_name in _iter_plugin_modules():
        try:
            module = importlib.import_module(module_name)
            plugin = _instantiate_plugin(module)
            if plugin is None:
                log.warning("No Plugin subclass found in %s", module_name)
                continue
            plugin.register(hooks)
            loaded.append(plugin.name)
            log.info("Loaded plugin: %s", plugin.name)
        except Exception:
            log.exception("Failed to load plugin module %s", module_name)
    return loaded
