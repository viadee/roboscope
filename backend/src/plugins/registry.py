"""Plugin registry: discovery, loading, management."""

import importlib
import logging
from pathlib import Path
from typing import Any

from src.plugins.base import BasePlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Manages plugin discovery, loading, and lifecycle."""

    def __init__(self):
        self._plugins: dict[str, BasePlugin] = {}
        self._plugin_classes: dict[str, type[BasePlugin]] = {}

    @property
    def plugins(self) -> dict[str, BasePlugin]:
        """Get all loaded plugins."""
        return self._plugins.copy()

    def discover_builtin(self) -> list[type[BasePlugin]]:
        """Discover built-in plugins from the builtin directory."""
        builtin_dir = Path(__file__).parent / "builtin"
        discovered: list[type[BasePlugin]] = []

        if not builtin_dir.exists():
            return discovered

        for py_file in builtin_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = f"src.plugins.builtin.{py_file.stem}"
            try:
                module = importlib.import_module(module_name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BasePlugin)
                        and attr is not BasePlugin
                        and hasattr(attr, "name")
                        and attr.name
                    ):
                        discovered.append(attr)
                        self._plugin_classes[attr.name] = attr
                        logger.info(f"Discovered plugin: {attr.name} ({attr.plugin_type})")
            except Exception as e:
                logger.error(f"Error discovering plugin from {py_file}: {e}")

        return discovered

    def discover_from_module(self, module_path: str) -> type[BasePlugin] | None:
        """Discover a plugin from a module path."""
        try:
            module = importlib.import_module(module_path)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin
                    and hasattr(attr, "name")
                    and attr.name
                ):
                    self._plugin_classes[attr.name] = attr
                    return attr
        except Exception as e:
            logger.error(f"Error loading module {module_path}: {e}")
        return None

    def load_plugin(self, name: str, config: dict | None = None) -> BasePlugin | None:
        """Load and initialize a plugin by name."""
        if name in self._plugins:
            return self._plugins[name]

        plugin_class = self._plugin_classes.get(name)
        if plugin_class is None:
            logger.error(f"Plugin class not found: {name}")
            return None

        try:
            instance = plugin_class()
            instance.initialize(config)
            self._plugins[name] = instance
            logger.info(f"Loaded plugin: {name}")
            return instance
        except Exception as e:
            logger.error(f"Error loading plugin {name}: {e}")
            return None

    def unload_plugin(self, name: str) -> None:
        """Unload a plugin and call its shutdown."""
        if name in self._plugins:
            try:
                self._plugins[name].shutdown()
            except Exception as e:
                logger.error(f"Error shutting down plugin {name}: {e}")
            del self._plugins[name]
            logger.info(f"Unloaded plugin: {name}")

    def get_plugin(self, name: str) -> BasePlugin | None:
        """Get a loaded plugin by name."""
        return self._plugins.get(name)

    def get_plugins_by_type(self, plugin_type: str) -> list[BasePlugin]:
        """Get all loaded plugins of a specific type."""
        return [p for p in self._plugins.values() if p.plugin_type == plugin_type]

    def shutdown_all(self) -> None:
        """Shutdown all loaded plugins."""
        for name in list(self._plugins.keys()):
            self.unload_plugin(name)


# Singleton registry
plugin_registry = PluginRegistry()
