# Sample plugin: convert text to uppercase on copy
NAME = "Better Shot"
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import io
from AppKit import NSPasteboard
from AppKit import NSPasteboardTypePNG
from Foundation import NSData

setting = {
    "background": "ffffff",
    "shadow": "000000",
    "auto_background": True,
    "auto_shadow": True,
    "margin": 50,
    "radius": 20,
    "edge_blur": 10,  # 縁取りブラーの強さ
    "edge_opacity": 0.5,  # 縁取りの不透明度(0.0-1.0)
    "watermark_type": "pf_blur",  # pf, pf_blur, watermark, logo, none
    "watermark_text": "｜@amania_jp",
    "watermark_image": "logo.png",
    "watermark_opacity": 0.8,
    "watermark_scale": 0.01,  # キャンバス幅に対する比率
    "pf_align": "center",  # center or left
    "pf_left_margin": 24,  # left 揃え時の左余白
    "pf_font_scale": 0.2,  # バー高さに対するフォント倍率
    "pf_font_min": 18,  # フォント最小値
    "wm_font_scale": 0.05,  # 透かし文字のキャンバス幅に対する倍率
    "wm_font_min": 24,  # 透かし文字の最小サイズ
}


def _parse_hex_color(hex_str):
    s = str(hex_str).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) == 6:
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        return (r, g, b, 255)
    if len(s) == 8:
        r, g, b, a = (
            int(s[0:2], 16),
            int(s[2:4], 16),
            int(s[4:6], 16),
            int(s[6:8], 16),
        )
        return (r, g, b, a)
    return (255, 255, 255, 255)


def _rounded_rect_mask(size, radius: int):
    """size=(w,h) の角丸矩形マスク(L)を作成。radius<=0 なら全不透明。"""
    w, h = size
    mask = Image.new("L", (w, h), 0)
    if radius and radius > 0:
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    else:
        mask.paste(255, (0, 0, w, h))
    return mask


def _apply_opacity(rgba, opacity: float):
    r, g, b, a = rgba
    op = max(0, min(1, float(opacity)))
    return (r, g, b, int(a * op))


def _load_font(size=48):
    # フォールバック付きのフォントロード
    candidates = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W1.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def generate_watermark(text=None, fill=(255, 255, 255, 160), size=48):
    text = text or setting.get("watermark_text") or ""
    font = _load_font(size)
    padding = int(size * 0.25)
    # テキストサイズを計算
    tmp_img = Image.new("RGBA", (10, 10))
    tmp_draw = ImageDraw.Draw(tmp_img)
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    watermark_size = (text_width + padding * 2, text_height + padding * 2)

    watermark = Image.new("RGBA", watermark_size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(watermark)
    draw.text((padding, padding), text, font=font, fill=fill)
    return watermark


def _auto_text_color(bg_img: Image.Image, box):
    # box=(x1,y1,x2,y2) の領域の平均輝度を見て白/黒を返す
    x1, y1, x2, y2 = [max(0, v) for v in box]
    x2 = min(bg_img.width, x2)
    y2 = min(bg_img.height, y2)
    if x2 <= x1 or y2 <= y1:
        # フォールバック: 白
        return (255, 255, 255, 230)
    region = bg_img.convert("L").crop((x1, y1, x2, y2)).resize((1, 1), Image.BILINEAR)
    lum = region.getpixel((0, 0))
    return (0, 0, 0, 230) if lum > 140 else (255, 255, 255, 230)


def _draw_text_on_image(
    img_rgba: Image.Image,
    text: str,
    align: str = "center",
    left_pad: int = None,
    logo_path: str = None,
    logo_opacity: float = 0.9,
    spacing_ratio: float = 0.25,
    font_scale: float = 0.05,
    font_min: int = 24,
    bottom_offset_ratio: float = 0.06,
):
    W, H = img_rgba.size
    fsize = max(int(font_min), int(H * float(font_scale)))
    font = _load_font(fsize)
    draw = ImageDraw.Draw(img_rgba)

    # テキストサイズ
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # ロゴ準備
    logo_img = None
    logo_w = logo_h = 0
    if logo_path and os.path.exists(logo_path):
        try:
            tmp_logo = Image.open(logo_path).convert("RGBA")
            target_h = max(12, int(th * 0.9))
            ratio = target_h / float(tmp_logo.height)
            logo_w = max(12, int(tmp_logo.width * ratio))
            logo_h = target_h
            logo_img = tmp_logo.resize((logo_w, logo_h), Image.LANCZOS)
            if logo_opacity < 1:
                r, g, b, a = logo_img.split()
                a = a.point(lambda v: int(v * max(0, min(1, logo_opacity))))
                logo_img = Image.merge("RGBA", (r, g, b, a))
        except Exception:
            logo_img = None
            logo_w = logo_h = 0

    spacing = max(6, int(th * spacing_ratio)) if logo_img is not None else 0
    cy = H - int(H * float(bottom_offset_ratio))

    if (align or "center").lower() == "left":
        lp = left_pad if left_pad is not None else max(12, int(W * 0.04))
        # サンプル領域と色決定
        tx = lp + (logo_w + spacing if logo_img is not None else 0)
        ty = cy - th // 2
        fill = _auto_text_color(img_rgba, (tx, ty, tx + tw, ty + th))
        # ロゴ
        if logo_img is not None:
            lx = lp
            ly = cy - logo_h // 2
            img_rgba.paste(logo_img, (lx, ly), logo_img)
        # テキスト
        try:
            draw.text((tx, cy), text, font=font, fill=fill, anchor="lm")
        except TypeError:
            draw.text((tx, ty), text, font=font, fill=fill)
        return img_rgba
    else:
        cx = W // 2
        tx = cx - tw // 2
        ty = cy - th // 2
        fill = _auto_text_color(img_rgba, (tx, ty, tx + tw, ty + th))
        # ロゴ
        if logo_img is not None:
            lx = cx - tw // 2 - spacing - logo_w
            ly = cy - logo_h // 2
            if lx < 0:
                lx = 0
            img_rgba.paste(logo_img, (lx, ly), logo_img)
        # テキスト
        try:
            draw.text((cx, cy), text, font=font, fill=fill, anchor="mm")
        except TypeError:
            draw.text((tx, ty), text, font=font, fill=fill)
        return img_rgba


def _add_bottom_bar(
    img_rgba,
    text: str,
    bar_ratio=0.12,
    offset_ratio=0.12,
    logo_path: str = None,
    logo_opacity: float = 0.9,
    spacing_ratio: float = 0.25,
    align: str = "center",
    left_pad=None,
    font_scale: float = 0.45,
    font_min: int = 18,
):
    # 画像下部に白バー + テキスト（Xiaomi 風）。
    # ロゴが指定されていれば、フォントサイズに合わせて左側に配置します。
    w, h = img_rgba.size
    bar_h = max(40, int(h * bar_ratio))
    out = Image.new("RGBA", (w, h + bar_h), (255, 255, 255, 255))
    out.paste(img_rgba, (0, 0), img_rgba)
    # テキストを中央に
    fsize = max(int(font_min), int(bar_h * float(font_scale)))
    font = _load_font(fsize)
    draw = ImageDraw.Draw(out)
    text_color = (0, 0, 0, 200)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # ロゴ読み込みとスケール（テキスト高さ基準）
    logo_img = None
    logo_w = logo_h = 0
    if logo_path and os.path.exists(logo_path):
        try:
            tmp_logo = Image.open(logo_path).convert("RGBA")
            target_h = max(12, min(th, int(bar_h * 0.85)))
            ratio = target_h / float(tmp_logo.height)
            logo_w = max(12, int(tmp_logo.width * ratio))
            logo_h = target_h
            logo_img = tmp_logo.resize((logo_w, logo_h), Image.LANCZOS)
            if logo_opacity < 1:
                r, g, b, a = logo_img.split()
                a = a.point(lambda v: int(v * max(0, min(1, logo_opacity))))
                logo_img = Image.merge("RGBA", (r, g, b, a))
        except Exception:
            logo_img = None
            logo_w = logo_h = 0

    spacing = 0
    if logo_img is not None:
        spacing = max(6, int(th * spacing_ratio))

    cy = h + bar_h // 2 - int(bar_h * float(offset_ratio))
    if (align or "center").lower() == "left":
        lp = left_pad if left_pad is not None else max(12, int(w * 0.04))
        # ロゴ配置（左）
        if logo_img is not None:
            lx = lp
            ly = cy - logo_h // 2
            out.paste(logo_img, (lx, ly), logo_img)
            lp = lx + logo_w + spacing
        # テキスト（左中揃え）
        try:
            draw.text((lp, cy), text, font=font, fill=text_color, anchor="lm")
        except TypeError:
            ty = cy - th // 2
            draw.text((lp, ty), text, font=font, fill=text_color)
    else:
        # 画像中心座標（バー内で上方向オフセット）
        cx = w // 2
        # ロゴをテキスト中央の左側に配置
        if logo_img is not None:
            lx = cx - tw // 2 - spacing - logo_w
            ly = cy - logo_h // 2
            if lx < 0:
                lx = 0  # はみ出し対策
            out.paste(logo_img, (lx, ly), logo_img)
        # テキスト描画（中央アンカー。未対応 Pillow はフォールバック）
        try:
            draw.text((cx, cy), text, font=font, fill=text_color, anchor="mm")
        except TypeError:
            tx_text = cx - tw // 2
            ty = cy - th // 2
            draw.text((tx_text, ty), text, font=font, fill=text_color)
    return out


def _overlay_logo(img_rgba, logo_path, scale=0.12, opacity=0.9, margin=16):
    if not logo_path or not os.path.exists(logo_path):
        return img_rgba
    logo = Image.open(logo_path).convert("RGBA")
    W, H = img_rgba.size
    target_w = max(16, int(W * float(scale)))
    ratio = target_w / float(logo.width)
    target_h = max(16, int(logo.height * ratio))
    logo = logo.resize((target_w, target_h), Image.LANCZOS)
    # 不透明度
    if opacity < 1:
        r, g, b, a = logo.split()
        a = a.point(lambda v: int(v * max(0, min(1, opacity))))
        logo = Image.merge("RGBA", (r, g, b, a))
    # 右下に配置
    pos = (W - target_w - margin, H - target_h - margin)
    out = img_rgba.copy()
    out.paste(logo, pos, logo)
    return out


def on_clipboard(data_type, value):
    if data_type == "image":
        img = value
        m = int(setting.get("margin", 0) or 0)
        radius = int(setting.get("radius", 0) or 0)
        blur = int(setting.get("edge_blur", 24) or 0)
        edge_opacity = float(setting.get("edge_opacity", 0.5) or 0.0)
        bg_color = _parse_hex_color(setting.get("background", "ffffff"))
        edge_color = _parse_hex_color(setting.get("shadow", "000000"))
        mode = (setting.get("watermark_type") or "none").lower()

        # ソース画像(RGBA)と角丸マスク
        src = img.convert("RGBA")
        w, h = src.size
        mask_inner = _rounded_rect_mask((w, h), radius)
        if radius > 0:
            src = Image.composite(
                src, Image.new("RGBA", (w, h), (0, 0, 0, 0)), mask_inner
            )

        # 出力キャンバス
        canvas_size = (w + m * 2, h + m * 2)
        if mode == "pf_blur":
            # 背景を元画像のブラーで埋める（Vivo 風）
            bg = src.resize(canvas_size, Image.LANCZOS).filter(
                ImageFilter.GaussianBlur(max(10, blur))
            )
            canvas = Image.new("RGBA", canvas_size)
            canvas.paste(bg, (0, 0))
            # ブラーの上にもテキスト/ロゴを載せる（自動白黒）
            # フォントサイズは margin-5 に固定し、位置は下マージン中央に来るように調整
            text = setting.get("watermark_text") or "Shot on CopyBento"
            H_total = canvas_size[1]
            bottom_offset = (m / float(2 * H_total)) if H_total > 0 else 0.08
            canvas = _draw_text_on_image(
                canvas,
                text,
                align=(setting.get("pf_align") or "center"),
                left_pad=int(setting.get("pf_left_margin", 24)),
                logo_path=setting.get("watermark_image"),
                logo_opacity=float(setting.get("watermark_opacity", 0.9)),
                spacing_ratio=0.25,
                font_scale=0.0,
                font_min=max(8, int(m) - 25),
                bottom_offset_ratio=max(0.0, min(0.5, bottom_offset)),
            )
        else:
            canvas = Image.new("RGBA", canvas_size, bg_color)

        # 縁取りブラー（外側グロー）
        if blur > 0:
            mask_outer = Image.new("L", canvas_size, 0)
            mask_outer.paste(mask_inner, (m, m))
            blurred = mask_outer.filter(ImageFilter.GaussianBlur(blur))
            glow_color = _apply_opacity(edge_color, edge_opacity)
            glow_layer = Image.new("RGBA", canvas_size, glow_color)
            canvas.paste(glow_layer, (0, 0), blurred)

        # 元画像（角丸適用済み）を重ねる
        canvas.paste(src, (m, m), mask_inner if radius > 0 else src)

        # 写真フレーム/ウォーターマーク適用
        if mode == "pf":
            text = setting.get("watermark_text") or "Shot on CopyBento"
            canvas = _add_bottom_bar(
                canvas,
                text,
                logo_path=setting.get("watermark_image"),
                logo_opacity=float(setting.get("watermark_opacity", 0.9)),
                align=(setting.get("pf_align") or "center"),
                left_pad=int(setting.get("pf_left_margin", 24)),
                font_scale=float(setting.get("pf_font_scale", 0.45)),
                font_min=int(setting.get("pf_font_min", 18)),
            )
        elif mode in ("watermark", "wotermark"):
            wm = generate_watermark(
                setting.get("watermark_text"),
                fill=(
                    255,
                    255,
                    255,
                    int(255 * float(setting.get("watermark_opacity", 0.8))),
                ),
                size=max(
                    int(setting.get("wm_font_min", 24)),
                    int((w + m * 2) * float(setting.get("wm_font_scale", 0.05))),
                ),
            )
            # 右下に配置
            W, H = canvas.size
            wm_w, wm_h = wm.size
            pos = (W - wm_w - max(8, m // 2), H - wm_h - max(8, m // 2))
            canvas.paste(wm, pos, wm)
        elif mode == "logo":
            canvas = _overlay_logo(
                canvas,
                setting.get("watermark_image"),
                scale=float(setting.get("watermark_scale", 0.12)),
                opacity=float(setting.get("watermark_opacity", 0.9)),
                margin=max(8, m // 2),
            )

        # 仕上げ: RGB に変換（背景あり）
        out = canvas.convert("RGB")
        # canvas.save("better_shot_output.jpg", "PNG")  # debug 保存したいとき有効化
        try:
            try:
                png_type = NSPasteboardTypePNG
            except Exception:
                png_type = "public.png"

            buf = io.BytesIO()
            out.save(buf, format="PNG")
            b = buf.getvalue()
            nsdata = NSData.dataWithBytes_length_(b, len(b))

            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setData_forType_(nsdata, png_type)
        except Exception:
            pass
        return ("image", out)
    return None
