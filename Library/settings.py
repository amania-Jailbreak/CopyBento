import json
import os
import shutil
from typing import Dict, Any


def _config_base() -> str:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = xdg if xdg else os.path.expanduser("~/.config")
    return os.path.join(base, "copybento")


def get_config_dir() -> str:
    """Return the CopyBento config directory (creates it if missing)."""
    path = _config_base()
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def _settings_path() -> str:
    return os.path.join(get_config_dir(), "settings.json")


def _migrate_old_settings_if_needed(new_path: str):
    # Migrate from old project-local settings.json if present
    try:
        old_base_dir = os.path.dirname(os.path.dirname(__file__))
        old_path = os.path.join(old_base_dir, "settings.json")
        if os.path.exists(old_path) and not os.path.exists(new_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.copy2(old_path, new_path)
    except Exception:
        pass


def _load_all() -> Dict[str, Any]:
    try:
        path = _settings_path()
        _migrate_old_settings_if_needed(path)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_all(data: Dict[str, Any]):
    try:
        path = _settings_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_plugins_enabled() -> Dict[str, bool]:
    data = _load_all()
    return dict(data.get("plugins", {}))


def set_plugin_enabled(name: str, enabled: bool):
    data = _load_all()
    plugins = dict(data.get("plugins", {}))
    plugins[name] = bool(enabled)
    data["plugins"] = plugins
    _save_all(data)


def set_plugins_enabled(enabled_map: Dict[str, bool]):
    data = _load_all()
    plugins = dict(data.get("plugins", {}))
    plugins.update({k: bool(v) for k, v in enabled_map.items()})
    data["plugins"] = plugins
    _save_all(data)
