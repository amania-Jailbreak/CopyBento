import json
import os
from typing import Dict, Any


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SETTINGS_JSON = os.path.join(BASE_DIR, "settings.json")


def _load_all() -> Dict[str, Any]:
    try:
        with open(SETTINGS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_all(data: Dict[str, Any]):
    try:
        with open(SETTINGS_JSON, "w", encoding="utf-8") as f:
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
