# mac_clipboard.py
#
# macOS専用のクリップボード操作モジュール
# 依存: pyobjc, pillow

from AppKit import NSPasteboard, NSStringPboardType, NSPasteboardTypePNG
from AppKit import NSImage
from Foundation import NSData
from PIL import Image
import io


class MacClipboard:
    @staticmethod
    def get_text():
        """クリップボードからテキストを取得"""
        pb = NSPasteboard.generalPasteboard()
        return pb.stringForType_(NSStringPboardType)

    @staticmethod
    def set_text(text: str):
        """クリップボードにテキストをコピー"""
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text, NSStringPboardType)

    @staticmethod
    def get_image():
        """クリップボードから画像を取得（Pillow Imageで返す）"""
        pb = NSPasteboard.generalPasteboard()
        data = pb.dataForType_(NSPasteboardTypePNG)
        if data is None:
            return None
        byte_array = bytes(data)
        return Image.open(io.BytesIO(byte_array))

    @staticmethod
    def set_image(image: Image.Image):
        """クリップボードに画像をコピー（Pillow Imageを受け取る）"""
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()

        # Pillow -> PNG バイト列
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        nsdata = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))

        # NSData を NSPasteboard に書き込む
        pb.setData_forType_(nsdata, NSPasteboardTypePNG)
