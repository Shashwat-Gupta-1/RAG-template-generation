from PIL import Image, ImageDraw, ImageFont
import os
from config import settings

FONT_MAP = {
    ("poppins",    "normal"):   "Poppins-Regular.ttf",
    ("poppins",    "bold"):     "Poppins-Bold.ttf",
    ("poppins",    "semibold"): "Poppins-SemiBold.ttf",
    ("notosans",   "normal"):   "NotoSans-Regular.ttf",
    ("notosans",   "bold"):     "NotoSans-Bold.ttf",
    ("notosans",   "semibold"): "NotoSans-Bold.ttf",
}

DEVANAGARI_MAP = {
    "normal":   "NotoSansDevanagari-Regular.ttf",
    "bold":     "NotoSansDevanagari-Bold.ttf",
    "semibold": "NotoSansDevanagari-Bold.ttf",
}


def _is_hindi(text: str) -> bool:
    return any("\u0900" <= c <= "\u097F" for c in text)


def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    fonts_dir = os.path.dirname(os.path.abspath(settings.font_path))
    path = os.path.join(fonts_dir, filename)
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    for fallback in [
        "NotoSansDevanagari-Regular.ttf",
        "NotoSans-Regular.ttf"
    ]:
        fp = os.path.join(fonts_dir, fallback)
        if os.path.exists(fp):
            print(f"Font '{filename}' not found — using {fallback}")
            return ImageFont.truetype(fp, size)
    print("WARNING: No TTF fonts found — using default (Hindi will not render)")
    return ImageFont.load_default()


def get_font(
    text: str,
    family: str,
    weight: str,
    size: int
) -> ImageFont.FreeTypeFont:
    if _is_hindi(text):
        filename = DEVANAGARI_MAP.get(
            weight.lower(), "NotoSansDevanagari-Regular.ttf"
        )
        return _load_font(filename, size)
    filename = FONT_MAP.get(
        (family.lower(), weight.lower()), "NotoSans-Regular.ttf"
    )
    return _load_font(filename, size)


def render_poster(
    template: dict,
    overlay_values: dict,
    output_path: str,
    uploaded_image_path: str = None,
    style_overrides: dict = None
) -> None:
    """
    Opens base PNG read-only. Stamps overlay values. Saves to output_path.
    style_overrides: {field_id: {font_family, font_size, color, ...}}
    """
    os.makedirs(settings.output_dir, exist_ok=True)
    style_overrides = style_overrides or {}

    if not os.path.exists(template["base_image"]):
        raise FileNotFoundError(
            f"Template PNG not found: {template['base_image']}"
        )

    img = Image.open(template["base_image"]).convert("RGBA")
    draw = ImageDraw.Draw(img)

    for layer in template.get("overlay_layers", []):
        if not layer.get("editable"):
            continue

        # Apply per-field style overrides (from live preview editor)
        style = dict(layer.get("style", {}))
        ov = style_overrides.get(layer.get("id", ""), {})
        for k, v in ov.items():
            if v is not None:
                style[k] = v

        if layer["type"] == "text":
            field_id = layer["id"]
            text = str(overlay_values.get(field_id, "") or "").strip()
            if not text:
                continue

            box = layer["box"]
            font_size = style.get("font_size", 48)
            font_size_min = style.get("font_size_min", 12)
            family = style.get("font_family", "Poppins")
            weight = style.get("font_weight", "normal")
            color = style.get("color", "#FFFFFF")
            align = style.get("align", "center")
            v_align = style.get("vertical_align", "middle")

            # Auto-shrink loop
            while font_size >= font_size_min:
                font = get_font(text, family, weight, font_size)
                bbox = draw.textbbox((0, 0), text, font=font)
                if (bbox[2] - bbox[0]) <= box["width"]:
                    break
                font_size -= 2

            font = get_font(text, family, weight, font_size)
            bbox = draw.textbbox((0, 0), text, font=font)

            # Truncate with ellipsis if still too wide
            original = text
            while (bbox[2] - bbox[0]) > box["width"] and len(text) > 1:
                text = text[:-1]
                font = get_font(text + "…", family, weight, font_size)
                bbox = draw.textbbox((0, 0), text + "…", font=font)
            if len(text) < len(original):
                text = text + "…"

            font = get_font(text, family, weight, font_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            if align == "center":
                draw_x = box["x"] + (box["width"] - text_w) // 2
            elif align == "right":
                draw_x = box["x"] + box["width"] - text_w
            else:
                draw_x = box["x"]

            if v_align == "middle":
                draw_y = box["y"] + (box["height"] - text_h) // 2
            elif v_align == "bottom":
                draw_y = box["y"] + box["height"] - text_h
            else:
                draw_y = box["y"]

            draw.text(
                (draw_x, draw_y), text, fill=color, font=font
            )

        elif layer["type"] == "image":
            if not uploaded_image_path:
                continue
            if not os.path.exists(uploaded_image_path):
                print(f"Uploaded image not found: {uploaded_image_path}")
                continue

            box = layer["box"]
            try:
                photo = Image.open(uploaded_image_path).convert("RGBA")
            except Exception as e:
                print(f"Could not open uploaded image: {e}")
                continue

            photo = photo.resize(
                (box["width"], box["height"]), Image.LANCZOS
            )

            if style.get("shape") == "circle":
                mask = Image.new("L", photo.size, 0)
                ImageDraw.Draw(mask).ellipse(
                    (0, 0, photo.size[0], photo.size[1]), fill=255
                )
                photo.putalpha(mask)
                border_w = style.get("border_width", 0)
                if border_w > 0:
                    rw = box["width"] + border_w * 2
                    rh = box["height"] + border_w * 2
                    ring = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
                    ImageDraw.Draw(ring).ellipse(
                        (0, 0, rw, rh),
                        fill=style.get("border_color", "#FFFFFF")
                    )
                    img.paste(
                        ring,
                        (box["x"] - border_w, box["y"] - border_w),
                        ring
                    )

            img.paste(photo, (box["x"], box["y"]), photo)

    img.save(output_path, format="PNG")