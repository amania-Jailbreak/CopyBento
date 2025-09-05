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
import threading

history = {}
MacClipboard = mcb.MacClipboard
plugins = PluginManager(os.path.join(os.path.dirname(__file__), "Plugins"))


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
    # Plugins can transform or skip the clipboard event
    processed = plugins.process(data_type, value)
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
            "All rights reserved by amania",
        ]
        # UI スレッド以外からの更新を避けるため、1秒ごとにメニューを再構築
        self._timer = rumps.Timer(self._refresh_history, 1.0)
        self._timer.start()

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
            plugins.set_enabled(name, not current)
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
        self.menu.clear()
        self.menu = [
            "CopyBento",
            rumps.separator,
            *self._build_history_items(),
            rumps.separator,
            self._build_plugin_items(),
            "All rights reserved by amania",
        ]

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
