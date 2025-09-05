import os
import json
import logging
import pyperclip
from Library import event
import time
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

event = event.EventManager()

# == Clipboard Monitoring ==

import time
from Library import mcb

history = {}
MacClipboard = mcb.MacClipboard


def wait_for_clipboard_change():
    """クリップボードの内容（テキスト or 画像）が変わるまで待機"""
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
    """Pillow Image同士を比較（同じならTrue）"""
    if img1 is None or img2 is None:
        return False
    return list(img1.getdata()) == list(img2.getdata())


event.add("clipboard_changed", wait_for_clipboard_change)


@event.event("clipboard_changed")
def on_clipboard_changed(data_type, value):
    if data_type == "text":
        logger.info(f"Clipboard changed (text): {value}")
    elif data_type == "image":
        logger.info(f"Clipboard changed (image)")
        value.show()

    # 変更履歴に追加
    history[time.time()] = (data_type, value)


asyncio.run(event.run(interval=0.1))
