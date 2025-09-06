import time
import asyncio
import inspect
import os
import logging


def _norm_combo(s: str):
    # Normalize combo like "Shift+Cmd+V" => (mods frozenset, key)
    if not s:
        return (frozenset(), "")
    parts = [p.strip().lower() for p in str(s).split("+") if p.strip()]
    key = parts[-1] if parts else ""
    mods_in = set(parts[:-1])
    # alias
    mapping = {
        "command": "cmd",
        "cmd": "cmd",
        "control": "ctrl",
        "ctl": "ctrl",
        "ctrl": "ctrl",
        "option": "alt",
        "opt": "alt",
        "alt": "alt",
        "shift": "shift",
    }
    mods = {mapping.get(m, m) for m in mods_in if m}
    return (frozenset(mods), key)


class EventManager:
    def __init__(self):
        # Registered callbacks and polling conditions
        self._handlers = {}  # イベント名 -> [ハンドラ関数リスト]
        self._conditions = {}  # イベント名 -> [発火条件関数リスト]
        # Hotkey support
        self._hotkeys = {}  # (mods, key) -> event_name
        self._hotkey_monitors_installed = False
        self._global_monitor = None
        self._local_monitor = None
        self._debug_keys = os.getenv("COPYBENTO_DEBUG_KEYS") == "1"

    def event(self, name):
        """デコレーターでイベント処理登録"""

        def decorator(func):
            self._handlers.setdefault(name, []).append(func)
            return func

        return decorator

    def add(self, name, condition_func):
        """トリガー条件を追加"""
        self._conditions.setdefault(name, []).append(condition_func)

    # ---- Hotkeys ----
    def register_hotkey(self, combo: str, event_name: str):
        """Register a hotkey like 'shift+cmd+v' to trigger an event name."""
        print(f"Register hotkey: {combo} -> {event_name}")
        self._hotkeys[_norm_combo(combo)] = event_name

    def _handle_key_event(self, ev):
        try:
            from Cocoa import (
                NSEventModifierFlagCommand,
                NSEventModifierFlagControl,
                NSEventModifierFlagOption,
                NSEventModifierFlagShift,
            )

            flags = int(ev.modifierFlags())
            mods = set()
            if flags & int(NSEventModifierFlagCommand):
                mods.add("cmd")
            if flags & int(NSEventModifierFlagControl):
                mods.add("ctrl")
            if flags & int(NSEventModifierFlagOption):
                mods.add("alt")
            if flags & int(NSEventModifierFlagShift):
                mods.add("shift")
            ch = (ev.charactersIgnoringModifiers() or "").lower()
            key = ch[-1] if ch else ""
            if self._debug_keys:
                logging.getLogger(__name__).info(
                    "KeyDown mods=%s key=%s", ",".join(sorted(mods)), key
                )
            event_name = self._hotkeys.get((frozenset(mods), key))
            if event_name:
                if self._debug_keys:
                    logging.getLogger(__name__).info(
                        "Trigger hotkey event: %s", event_name
                    )
                self.trigger(event_name)
        except Exception:
            pass

    def install_hotkey_monitors_on_main_thread(self):
        if self._hotkey_monitors_installed:
            return
        try:
            from Cocoa import NSEvent, NSEventMaskKeyDown

            def _global(ev):
                self._handle_key_event(ev)

            def _local(ev):
                self._handle_key_event(ev)
                return ev

            # グローバル/ローカル両方の監視を入れる（参照を保持）
            self._global_monitor = (
                NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                    NSEventMaskKeyDown, _global
                )
            )
            self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown, _local
            )
            self._hotkey_monitors_installed = True
        except Exception:
            # Cocoaが利用できない場合は無視
            self._hotkey_monitors_installed = False

    def trigger(self, name, *args, **kwargs):
        """イベント発火"""
        for func in self._handlers.get(name, []):
            func(*args, **kwargs)

    async def run(self, interval=0.5):
        while True:
            for name, conditions in self._conditions.items():
                for cond in conditions:
                    result = cond()  # <- ここで wait_for_clipboard_change() が返す
                    if result:  # None でなければ trigger に渡す
                        self.trigger(name, *result)  # data_type, value が渡る
            await asyncio.sleep(interval)
