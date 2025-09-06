import importlib.util
import logging
import os
from types import ModuleType
from typing import Any, List, Tuple


logger = logging.getLogger(__name__)


class PluginManager:
    """
    Simple plugin manager for CopyBento.

    Plugin module contract:
      - Define a callable `on_clipboard(data_type, value)`.
        * Return None to leave unchanged
        * Return ("text", new_text) or ("image", new_image) to modify
        * Return PluginManager.SKIP or ("skip", None) to drop the event
      - Optional: NAME (str) for display/logging
    """

    SKIP = object()

    def __init__(self, plugin_dir: str):
        self.plugin_dir = plugin_dir
        self.plugins: List[dict] = []  # {name, module, enabled}
        self.load_all()

    def load_all(self):
        if not os.path.isdir(self.plugin_dir):
            logger.info("Plugin directory not found: %s", self.plugin_dir)
            return
        for fname in sorted(os.listdir(self.plugin_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            path = os.path.join(self.plugin_dir, fname)
            name = os.path.splitext(fname)[0]
            try:
                spec = importlib.util.spec_from_file_location(
                    f"copybento_plugins.{name}", path
                )
                if spec is None or spec.loader is None:
                    raise RuntimeError("Invalid spec for plugin: %s" % path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                if hasattr(mod, "on_clipboard") and callable(
                    getattr(mod, "on_clipboard")
                ):
                    display = getattr(mod, "NAME", name)
                    self.plugins.append(
                        {
                            "name": display,  # display name (NAME)
                            "key": name,  # module basename
                            "module": mod,
                            "enabled": True,
                        }
                    )
                    logger.info("Loaded plugin: %s", display)
                else:
                    logger.warning("Plugin %s missing on_clipboard(); skipped", fname)
            except Exception as e:
                logger.exception("Failed to load plugin %s: %s", fname, e)

    def process(self, data_type: str, value: Any):
        current_type, current_value = data_type, value
        for p in self.plugins:
            if not p.get("enabled", True):
                continue
            mod: ModuleType = p["module"]
            try:
                out = mod.on_clipboard(current_type, current_value)  # type: ignore[attr-defined]
                if out is None:
                    continue
                # Allow sentinel or tuple ('skip', None)
                if out is self.SKIP or (isinstance(out, tuple) and out[0] == "skip"):
                    logger.info("Plugin %s skipped the clipboard item", p["name"])
                    return self.SKIP
                if (
                    isinstance(out, tuple)
                    and len(out) == 2
                    and out[0] in ("text", "image")
                ):
                    current_type, current_value = out
            except Exception as e:
                logger.exception("Plugin %s failed: %s", p["name"], e)
                continue
        return (current_type, current_value)

    def list_plugins(self) -> List[Tuple[str, bool]]:
        return [(p["name"], bool(p.get("enabled", True))) for p in self.plugins]

    def set_enabled(self, name: str, enabled: bool):
        """Enable/disable a plugin by display NAME or module key."""
        for p in self.plugins:
            if p.get("name") == name or p.get("key") == name:
                p["enabled"] = enabled
                return True
        return False
