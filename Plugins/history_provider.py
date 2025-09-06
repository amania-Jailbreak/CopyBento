NAME = "History Provider"
import os, json

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
HIST_DIR = os.path.join(BASE_DIR, "History")
HIST_JSON = os.path.join(HIST_DIR, "history.json")


def on_clipboard(data_type, value):
    # This plugin does not transform clipboard content
    return None


def get_history():
    try:
        with open(HIST_JSON, "r", encoding="utf-8") as f:
            items = json.load(f)
            # Validate minimal shape
            out = []
            for it in items:
                t = it.get("type")
                if t not in ("text", "image"):
                    continue
                # Ensure preview
                if t == "text":
                    txt = it.get("text") or ""
                    it["preview"] = (txt[:100] + "...") if len(txt) > 100 else txt
                else:
                    it.setdefault("preview", "[Image]")
                out.append(it)
            out.sort(key=lambda r: r.get("ts", 0), reverse=True)
            return out
    except Exception:
        return []


def on_startup(event_manager):
    # Example: plugins can register hotkeys here if desired
    # event_manager.register_hotkey("shift+cmd+v", "open_history_gui")
    pass
