import time
import asyncio
import inspect


class EventManager:
    def __init__(self):
        self._handlers = {}  # イベント名 -> [ハンドラ関数リスト]
        self._conditions = {}  # イベント名 -> [発火条件関数リスト]

    def event(self, name):
        """デコレーターでイベント処理登録"""

        def decorator(func):
            self._handlers.setdefault(name, []).append(func)
            return func

        return decorator

    def add(self, name, condition_func):
        """トリガー条件を追加"""
        self._conditions.setdefault(name, []).append(condition_func)

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
