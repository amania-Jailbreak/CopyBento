import os
import json
import logging
import pyperclip
from Library import event
import time
import asyncio
import rumps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

event = event.EventManager()

# == Clipboard Monitoring ==

import time
from Library import mcb
from Library.plugin import PluginManager
from Library import settings as app_settings
import threading

history = {}
MacClipboard = mcb.MacClipboard
plugins = PluginManager(os.path.join(os.path.dirname(__file__), "Plugins"))

# Apply persisted plugin enabled states BEFORE startup hooks
try:
    persisted = app_settings.get_plugins_enabled()
    for p in plugins.plugins:
        try:
            desired = persisted.get(
                p.get("name"), persisted.get(p.get("key"), p.get("enabled", True))
            )
            p["enabled"] = bool(desired)
        except Exception:
            pass
except Exception:
    pass


# == Permissions ==
def _ensure_accessibility_permission():
    """Request Accessibility permission (shows system prompt if not granted)."""
    trusted = False
    # Try Quartz.CoreGraphics first (most common in PyObjC)
    try:
        from Quartz import CoreGraphics as CG

        try:
            opts = {CG.kAXTrustedCheckOptionPrompt: True}
            trusted = bool(CG.AXIsProcessTrustedWithOptions(opts))
        except Exception:
            # Fall back to non-prompting check if options API missing
            try:
                trusted = bool(CG.AXIsProcessTrusted())
            except Exception:
                pass
    except Exception:
        pass

    # Try ApplicationServices module (some environments expose the AX API here)
    if not trusted:
        try:
            from ApplicationServices import (
                AXIsProcessTrustedWithOptions,
                kAXTrustedCheckOptionPrompt,
            )

            opts = {kAXTrustedCheckOptionPrompt: True}
            trusted = bool(AXIsProcessTrustedWithOptions(opts))
        except Exception:
            pass

    # Try loading from HIServices via objc bundle to avoid import-time symbol issues
    if not trusted:
        try:
            import objc

            hiservices = objc.loadBundle(
                "HIServices",
                globals(),
                bundle_path="/System/Library/Frameworks/ApplicationServices.framework/Frameworks/HIServices.framework",
            )
            funcs = [("AXIsProcessTrustedWithOptions", b"Z@")]
            consts = [("kAXTrustedCheckOptionPrompt", b"@")]
            objc.loadBundleFunctions(hiservices, globals(), funcs)
            objc.loadBundleVariables(hiservices, globals(), consts)
            try:
                opts = {kAXTrustedCheckOptionPrompt: True}  # type: ignore[name-defined]
                trusted = bool(AXIsProcessTrustedWithOptions(opts))  # type: ignore[name-defined]
            except Exception:
                pass
        except Exception:
            pass

    if not trusted:
        # Log lightly and show a user-facing alert; continue without crashing
        logger.warning(
            "Accessibility check not available or not granted; continuing without prompt"
        )
        try:
            rumps.alert(
                "Permission Required",
                "キーボードショートカットを使うには『アクセシビリティ』の許可が必要です。\nシステム設定 > プライバシーとセキュリティ > アクセシビリティ で Python/CopyBento を有効にしてください。",
            )
        except Exception:
            pass
    return trusted

    if not trusted:
        try:
            rumps.alert(
                "Permission Required",
                "キーボードショートカットを使うには『アクセシビリティ』の許可が必要です。\nシステム設定 > プライバシーとセキュリティ > アクセシビリティ で Python/CopyBento を有効にしてください。",
            )
        except Exception:
            pass
    return trusted


def _open_accessibility_pane():
    """Open System Settings to the Accessibility privacy pane (best-effort)."""
    try:
        import subprocess

        # Works on recent macOS versions
        subprocess.Popen(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ]
        )
    except Exception:
        pass


# Let plugins do startup registration (e.g., register hotkeys) only if enabled
for p in plugins.plugins:
    if not p.get("enabled", True):
        continue
    try:
        mod = p.get("module")
        if mod and hasattr(mod, "on_startup") and callable(mod.on_startup):
            mod.on_startup(event)
    except Exception:
        pass

# Hotkeys and GUI opener are registered by Plugins/GUI.py:on_startup

# == History persistence for GUI ==
BASE_DIR = os.path.dirname(__file__)
HIST_DIR = os.path.join(BASE_DIR, "History")
HIST_JSON = os.path.join(HIST_DIR, "history.json")

os.makedirs(HIST_DIR, exist_ok=True)


def _load_history_file():
    try:
        with open(HIST_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history_file(items):
    try:
        with open(HIST_JSON, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("Failed to save history.json: %s", e)


def _persist_history(ts: float, data_type: str, value):
    items = _load_history_file()
    record = {"ts": ts, "type": data_type}
    if data_type == "text":
        text = value if isinstance(value, str) else str(value)
        record["text"] = text
        record["preview"] = (text[:100] + "...") if len(text) > 100 else text
    elif data_type == "image":
        try:
            from PIL import Image

            # 保存先パス
            fname = f"img_{int(ts*1000)}.png"
            fpath = os.path.join(HIST_DIR, fname)
            value.convert("RGBA").save(fpath, "PNG")
            record["image_path"] = fpath
            record["preview"] = "[Image]"
        except Exception as e:
            logger.exception("Failed to persist image: %s", e)
            return
    items.append(record)
    # 最新200件に制限
    items = sorted(items, key=lambda r: r.get("ts", 0), reverse=True)[:200]
    _save_history_file(items)


def wait_for_clipboard_change():
    last_text = MacClipboard.get_text()
    last_img = MacClipboard.get_image()

    while True:
        time.sleep(0.5)
        current_text = MacClipboard.get_text()
        current_img = MacClipboard.get_image()

        # テキストの変化検出
        if current_text != last_text and current_text is not None:
            last_text = current_text
            return ("text", current_text)

        # 画像の変化検出（バイト比較すると確実）
        if (current_img is not None) and not images_equal(current_img, last_img):
            last_img = current_img

            return ("image", current_img)


def images_equal(img1, img2):
    if img1 is None or img2 is None:
        return False
    return list(img1.getdata()) == list(img2.getdata())


event.add("clipboard_changed", wait_for_clipboard_change)


@event.event("clipboard_changed")
def on_clipboard_changed(data_type, value):
    # GUI からの画像コピーはプラグイン適用をスキップ
    if data_type == "image":
        try:
            mark = MacClipboard.get_source_marker()
        except Exception:
            mark = None
        if mark and str(mark).lower().startswith("gui"):
            processed = (data_type, value)
        else:
            processed = plugins.process(data_type, value)
    else:
        # Plugins can transform or skip the clipboard event
        processed = plugins.process(data_type, value)
    print(processed)
    if processed is PluginManager.SKIP:
        logger.info("Clipboard event skipped by plugin")
        return
    data_type, value = processed
    print(f"Processed clipboard: {data_type}, {type(value)}")
    if data_type == "text":
        logger.info(f"Clipboard changed (text): {value}")
    elif data_type == "image":
        logger.info(f"Clipboard changed (image)")

    # 変更履歴に追加
    history[time.time()] = (data_type, value)
    # 永続化（GUI 用）
    try:
        _persist_history(list(history.keys())[-1], data_type, value)
    except Exception:
        pass


# == macOS menuBar ==


class ClipboardMonitorApp(rumps.App):
    def __init__(self):
        super(ClipboardMonitorApp, self).__init__("CopyBento")
        # クラス内の履歴は使わず、下の history(dict) を参照する
        self.history = []  # 互換のために残すが未使用
        # Build plugin toggle submenu
        plugin_items = self._build_plugin_items()

        self.menu = [
            "CopyBento",
            rumps.separator,
            *self._build_history_items(),
            rumps.separator,
            plugin_items,
            rumps.MenuItem(
                "Open Accessibility Settings", callback=self._open_accessibility_cb
            ),
            "All rights reserved by amania",
        ]
        # UI スレッド以外からの更新を避けるため、1秒ごとにメニューを再構築
        self._timer = rumps.Timer(self._refresh_history, 1.0)
        self._timer.start()
        # Ensure hotkeys are installed on main thread
        try:
            event.install_hotkey_monitors_on_main_thread()
        except Exception:
            pass

        # Accessibility permission prompt (delayed so status item appears first)
        try:
            self._acc_timer = rumps.Timer(
                lambda _: _ensure_accessibility_permission(), 0.3
            )
            self._acc_timer.start()
        except Exception:
            try:
                _ensure_accessibility_permission()
            except Exception:
                pass
        # Optional: show a one-time startup notification to confirm residency
        try:
            rumps.notification("CopyBento", "Running", "Menu bar app started")
        except Exception:
            pass

    def _build_history_items(self):
        items_out = []
        # 直近の履歴 20 件を新しい順で表示
        try:
            items = sorted(history.items(), key=lambda kv: kv[0], reverse=True)[:20]
        except Exception:
            items = []

        if not items:
            items_out.append(
                rumps.MenuItem("(No history yet)", callback=lambda _: None)
            )
            return items_out

        for idx, (_ts, (data_type, value)) in enumerate(items):
            if data_type == "text":
                text = value if isinstance(value, str) else str(value)
                preview = (text[:100] + "...") if len(text) > 100 else text
                title = f"{idx+1}: {preview}"
            else:
                title = f"{idx+1}: [Image]"

            items_out.append(
                rumps.MenuItem(
                    title, callback=self.create_history_callback(data_type, value)
                )
            )

        return items_out

    def _build_plugin_items(self):
        submenu = rumps.MenuItem("Plugins")
        for name, enabled in plugins.list_plugins():
            item = rumps.MenuItem(
                f"{'✅' if enabled else '❌'} {name}",
                callback=self._toggle_plugin_cb(name),
            )
            submenu.add(item)
        if not submenu._menu:  # type: ignore[attr-defined]
            submenu.add(rumps.MenuItem("(No plugins)", callback=lambda _: None))
        return submenu

    def _toggle_plugin_cb(self, name: str):
        def _cb(_):
            # Toggle state
            current = dict(plugins.list_plugins()).get(name, True)
            new_state = not current
            plugins.set_enabled(name, new_state)
            # Persist both display name and module key for compatibility
            try:
                for p in plugins.plugins:
                    if p.get("name") == name:
                        key = p.get("key") or name
                        app_settings.set_plugins_enabled(
                            {name: new_state, key: new_state}
                        )
                        break
            except Exception:
                pass
            # refresh plugin menu immediately
            self._refresh_history(None)

        return _cb

    def create_history_callback(self, data_type, value):
        def _cb(_):
            try:
                if data_type == "text":
                    MacClipboard.set_text(value)
                    rumps.notification(
                        "CopyBento", "Copied from History", "Text item copied"
                    )
                else:
                    MacClipboard.set_image(value)
                    rumps.notification(
                        "CopyBento", "Copied from History", "Image item copied"
                    )
            except Exception as e:
                logger.exception("Failed to copy from history: %s", e)
                rumps.notification("CopyBento", "Error", str(e))

        return _cb

    def _refresh_history(self, _):
        # ルートメニューを再構築（軽量なため簡易実装）
        # Apply persisted plugin states so GUI settings take effect without restart
        try:
            persisted = app_settings.get_plugins_enabled()
            for p in plugins.plugins:
                desired = persisted.get(
                    p.get("name"), persisted.get(p.get("key"), p.get("enabled", True))
                )
                if bool(p.get("enabled", True)) != bool(desired):
                    # Allow either key or name
                    plugins.set_enabled(p.get("key") or p.get("name"), bool(desired))
        except Exception:
            pass
        self.menu.clear()
        self.menu = [
            "CopyBento",
            rumps.separator,
            *self._build_history_items(),
            rumps.separator,
            self._build_plugin_items(),
            "All rights reserved by amania",
        ]

    def _open_accessibility_cb(self, _):
        _open_accessibility_pane()

    # immediate refresh


app = ClipboardMonitorApp()


# Run the async EventManager in a background thread
_loop = asyncio.new_event_loop()


def _run_asyncio():
    asyncio.set_event_loop(_loop)
    _loop.create_task(event.run(interval=0.1))
    _loop.run_forever()


threading.Thread(target=_run_asyncio, daemon=True).start()

# Run the menu bar app on the main thread
app.run()
