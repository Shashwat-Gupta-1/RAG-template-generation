"""Standalone template renderer.

This module renders an overlay.json template directly onto its base image.
It intentionally avoids the RAG/indexer/config stack so it can be used in
isolation for local testing and preview generation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WINDOWS_FONTS_DIR = Path("C:/Windows/Fonts")

SCRIPT_PATTERNS: dict[str, re.Pattern[str]] = {
	"devanagari": re.compile(r"[\u0900-\u097F]"),
	"bengali": re.compile(r"[\u0980-\u09FF]"),
	"gurmukhi": re.compile(r"[\u0A00-\u0A7F]"),
	"gujarati": re.compile(r"[\u0A80-\u0AFF]"),
	"oriya": re.compile(r"[\u0B00-\u0B7F]"),
	"tamil": re.compile(r"[\u0B80-\u0BFF]"),
	"telugu": re.compile(r"[\u0C00-\u0C7F]"),
	"kannada": re.compile(r"[\u0C80-\u0CFF]"),
	"malayalam": re.compile(r"[\u0D00-\u0D7F]"),
}

SCRIPT_DEFAULT_FAMILIES: dict[str, list[str]] = {
	"devanagari": ["NotoSansDevanagari", "NotoSerifDevanagari", "Mukta", "Mangal", "Nirmala UI"],
	"bengali": ["NotoSansBengali", "NotoSerifBengali", "Vrinda", "Nirmala UI"],
	"gurmukhi": ["NotoSansGurmukhi", "NotoSerifGurmukhi", "Raavi", "Nirmala UI"],
	"gujarati": ["NotoSansGujarati", "NotoSerifGujarati", "Shruti", "Nirmala UI"],
	"oriya": ["NotoSansOriya", "NotoSerifOriya", "Kalinga", "Nirmala UI"],
	"tamil": ["NotoSansTamil", "NotoSerifTamil", "Latha", "Vijaya", "Nirmala UI"],
	"telugu": ["NotoSansTelugu", "NotoSerifTelugu", "Gautami", "Nirmala UI"],
	"kannada": ["NotoSansKannada", "NotoSerifKannada", "Tunga", "Nirmala UI"],
	"malayalam": ["NotoSansMalayalam", "NotoSerifMalayalam", "Kartika", "Nirmala UI"],
}

WINDOWS_FONT_HINTS: dict[str, list[str]] = {
	"devanagari": ["Mangal.ttf", "MangalB.ttf", "Nirmala.ttf", "NirmalaB.ttf", "Aparaj.ttf", "Kokila.ttf", "Kokilab.ttf"],
	"bengali": ["Nirmala.ttf", "NirmalaB.ttf", "Vrinda.ttf"],
	"gurmukhi": ["Nirmala.ttf", "NirmalaB.ttf", "Raavi.ttf"],
	"gujarati": ["Nirmala.ttf", "NirmalaB.ttf", "Shruti.ttf"],
	"oriya": ["Nirmala.ttf", "NirmalaB.ttf", "Kalinga.ttf"],
	"tamil": ["Nirmala.ttf", "NirmalaB.ttf", "Latha.ttf", "Vijaya.ttf"],
	"telugu": ["Nirmala.ttf", "NirmalaB.ttf", "Gautami.ttf"],
	"kannada": ["Nirmala.ttf", "NirmalaB.ttf", "Tunga.ttf"],
	"malayalam": ["Nirmala.ttf", "NirmalaB.ttf", "Kartika.ttf", "KartikaB.ttf"],
}

GLOBAL_FONT_FALLBACK = ["Poppins", "NotoSans"]

# Maps friendly font family names (lowercase) → actual Windows TTF filenames.
# Regular listed first; bold variant second so bold requests prefer the bd file.
SYSTEM_FONT_ALIASES: dict[str, list[str]] = {
	"times new roman": ["times.ttf", "timesbd.ttf"],
	"arial":           ["arial.ttf", "arialbd.ttf"],
	"calibri":         ["calibri.ttf", "calibrib.ttf"],
	"verdana":         ["verdana.ttf", "verdanab.ttf"],
	"georgia":         ["georgia.ttf", "georgiab.ttf"],
	"trebuchet ms":    ["trebuc.ttf", "trebucbd.ttf"],
	"comic sans ms":   ["comic.ttf", "comicbd.ttf"],
	"courier new":     ["cour.ttf", "courbd.ttf"],
	"tahoma":          ["tahoma.ttf", "tahomabd.ttf"],
	"segoe ui":        ["segoeui.ttf", "segoeuib.ttf"],
}


def _detect_scripts(text: str) -> set[str]:
	scripts: set[str] = set()
	for script_name, pattern in SCRIPT_PATTERNS.items():
		if pattern.search(text):
			scripts.add(script_name)
	return scripts


def _font_name_variants(font_name: str, font_weight: str | None = None) -> list[str]:
	normalized_name = font_name.strip()
	if not normalized_name:
		return []

	name_path = Path(normalized_name)
	if name_path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
		return [normalized_name]

	aliases = {normalized_name, normalized_name.replace(" ", "")}
	variants: list[str] = []
	weight_key = (font_weight or "").strip().lower()
	weight_variants = ["Regular", "Medium", "SemiBold", "Bold"]
	if weight_key in {"bold", "700", "800", "900"}:
		weight_variants = ["Bold", "SemiBold", "Medium", "Regular"]
	elif weight_key in {"semibold", "600"}:
		weight_variants = ["SemiBold", "Bold", "Medium", "Regular"]

	for alias in aliases:
		variants.append(f"{alias}.ttf")
		for weight_variant in weight_variants:
			variants.append(f"{alias}-{weight_variant}.ttf")
			variants.append(f"{alias} {weight_variant}.ttf")

	seen: set[str] = set()
	unique_variants: list[str] = []
	for variant in variants:
		if variant not in seen:
			seen.add(variant)
			unique_variants.append(variant)
	return unique_variants


def _font_candidate_paths(font_families: Sequence[str], font_weight: str | None = None, scripts: set[str] | None = None) -> list[Path]:
	font_candidates: list[Path] = []
	resolved_scripts = scripts or set()
	weight_key = (font_weight or "").strip().lower()
	is_bold_weight = weight_key in {"bold", "700", "800", "900", "semibold", "600"}

	for script_name in resolved_scripts:
		hinted_filenames = WINDOWS_FONT_HINTS.get(script_name, [])
		if is_bold_weight:
			hinted_filenames = sorted(
				hinted_filenames,
				key=lambda name: (0 if ("bold" in name.lower() or name.lower().endswith("b.ttf")) else 1, name.lower()),
			)
		for hinted_filename in hinted_filenames:
			font_candidates.append(WINDOWS_FONTS_DIR / hinted_filename)
		for family in SCRIPT_DEFAULT_FAMILIES.get(script_name, []):
			for variant in _font_name_variants(family, font_weight):
				font_candidates.append(_resolve_path(Path("fonts") / variant))
				font_candidates.append(_resolve_path(variant))
				font_candidates.append(WINDOWS_FONTS_DIR / variant)

	for family in font_families:
		# ── Check system alias table first (exact Windows filenames) ──────
		alias_files = SYSTEM_FONT_ALIASES.get(family.strip().lower(), [])
		if is_bold_weight and len(alias_files) > 1:
			# Prefer bold variant (second entry) when bold weight requested
			alias_files = [alias_files[1], alias_files[0]]
		for alias_file in alias_files:
			font_candidates.append(WINDOWS_FONTS_DIR / alias_file)
		# ── Then try generated name variants ──────────────────────────────
		for variant in _font_name_variants(family, font_weight):
			font_candidates.append(_resolve_path(Path("fonts") / variant))
			font_candidates.append(_resolve_path(variant))
			font_candidates.append(WINDOWS_FONTS_DIR / variant)

	for family in GLOBAL_FONT_FALLBACK:
		for variant in _font_name_variants(family, font_weight):
			font_candidates.append(_resolve_path(Path("fonts") / variant))
			font_candidates.append(_resolve_path(variant))
			font_candidates.append(WINDOWS_FONTS_DIR / variant)

	seen: set[Path] = set()
	unique_candidates: list[Path] = []
	for candidate in font_candidates:
		if candidate not in seen:
			seen.add(candidate)
			unique_candidates.append(candidate)
	return unique_candidates


def _resolve_path(raw_path: str | Path) -> Path:
	path = Path(raw_path)
	if path.is_absolute():
		return path
	return PROJECT_ROOT / path


def _normalize_text(value: Any) -> str:
	if value is None:
		return ""
	if isinstance(value, str):
		return value.strip()
	return str(value)


def _is_bold_weight(font_weight: str | None) -> bool:
	weight_key = _normalize_text(font_weight).lower()
	return weight_key in {"bold", "700", "800", "900", "semibold", "600"}


def load_overlay_json(overlay_path: str | Path) -> Dict[str, Any]:
	resolved_path = _resolve_path(overlay_path)
	with resolved_path.open("r", encoding="utf-8") as handle:
		return json.load(handle)


def _load_base_image(overlay: Mapping[str, Any]) -> Image.Image:
	canvas = overlay.get("canvas") or {}
	canvas_width = int(canvas.get("width") or 1200)
	canvas_height = int(canvas.get("height") or 1200)
	base_image_path = overlay.get("base_image")

	if base_image_path:
		resolved_base_image_path = _resolve_path(str(base_image_path))
		if resolved_base_image_path.exists():
			base_image = Image.open(resolved_base_image_path).convert("RGBA")
			if base_image.size != (canvas_width, canvas_height):
				base_image = base_image.resize((canvas_width, canvas_height), Image.LANCZOS)
			return base_image

	return Image.new("RGBA", (canvas_width, canvas_height), "white")


def _load_font(
	font_families: Sequence[str],
	font_size: int,
	font_weight: str | None = None,
	scripts: set[str] | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
	for candidate in _font_candidate_paths(font_families, font_weight, scripts):
		if candidate.exists():
			try:
				return ImageFont.truetype(str(candidate), font_size)
			except OSError:
				continue

	return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
	words = text.split()
	if not words:
		return [""]

	lines: list[str] = []
	current_line = words[0]
	for word in words[1:]:
		candidate = f"{current_line} {word}"
		bbox = draw.textbbox((0, 0), candidate, font=font)
		if bbox[2] - bbox[0] <= max_width:
			current_line = candidate
		else:
			lines.append(current_line)
			current_line = word
	lines.append(current_line)
	return lines


def _fit_font_to_box(
	draw: ImageDraw.ImageDraw,
	text: str,
	box: Mapping[str, Any],
	style: Mapping[str, Any],
	font_families: Sequence[str],
	scripts: set[str] | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
	font_weight = _normalize_text(style.get("font_weight")) or None
	is_bold = _is_bold_weight(font_weight)
	max_size = int(style.get("font_size") or 48)
	min_size = int(style.get("font_size_min") or max(12, max_size // 2))
	box_width = int(box.get("width") or 0)
	box_height = int(box.get("height") or 0)

	for size in range(max_size, min_size - 1, -2):
		font = _load_font(font_families, size, font_weight, scripts)
		lines = _wrap_text(draw, text, font, box_width)
		line_boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
		line_heights = [(bounds[3] - bounds[1]) for bounds in line_boxes]
		line_spacing = max(2, size // 5)
		total_height = sum(line_heights) + line_spacing * max(0, len(lines) - 1)
		max_line_width = max((bounds[2] - bounds[0]) for bounds in line_boxes) if line_boxes else 0
		if max_line_width <= box_width and total_height <= box_height:
			return font

	return _load_font(font_families, min_size, font_weight, scripts)


def _script_default_families(scripts: set[str]) -> list[str]:
	defaults: list[str] = []
	for script_name in scripts:
		defaults.extend(SCRIPT_DEFAULT_FAMILIES.get(script_name, []))
	seen: set[str] = set()
	unique_defaults: list[str] = []
	for family in defaults:
		family_key = family.lower()
		if family_key not in seen:
			seen.add(family_key)
			unique_defaults.append(family)
	return unique_defaults


def _extract_value_candidates(style: Mapping[str, Any]) -> list[str]:
	candidates: list[str] = []
	font_family = _normalize_text(style.get("font_family"))
	if font_family:
		candidates.append(font_family)
	font_fallback = style.get("font_fallback")
	if isinstance(font_fallback, str) and font_fallback.strip():
		candidates.extend(part.strip() for part in font_fallback.split(",") if part.strip())
	elif isinstance(font_fallback, list):
		candidates.extend(_normalize_text(part) for part in font_fallback if _normalize_text(part))
	return candidates


def _merge_font_families(primary: Sequence[str], fallback: Sequence[str]) -> list[str]:
	merged: list[str] = []
	seen: set[str] = set()
	for family in [*primary, *fallback]:
		normalized = _normalize_text(family)
		if not normalized:
			continue
		key = normalized.lower()
		if key in seen:
			continue
		seen.add(key)
		merged.append(normalized)
	return merged


# ── Windows GDI Drawing Helpers (for Devnagari / complex scripts layout) ──────
import ctypes
from ctypes import wintypes

class BITMAPINFOHEADER(ctypes.Structure):
	_fields_ = [
		("biSize", wintypes.DWORD),
		("biWidth", wintypes.LONG),
		("biHeight", wintypes.LONG),
		("biPlanes", wintypes.WORD),
		("biBitCount", wintypes.WORD),
		("biCompression", wintypes.DWORD),
		("biSizeImage", wintypes.DWORD),
		("biXPelsPerMeter", wintypes.LONG),
		("biYPelsPerMeter", wintypes.LONG),
		("biClrUsed", wintypes.DWORD),
		("biClrImportant", wintypes.DWORD),
	]

class BITMAPINFO(ctypes.Structure):
	_fields_ = [
		("bmiHeader", BITMAPINFOHEADER),
		("bmiColors", wintypes.DWORD * 3),
	]

class RECT(ctypes.Structure):
	_fields_ = [
		("left", wintypes.LONG),
		("top", wintypes.LONG),
		("right", wintypes.LONG),
		("bottom", wintypes.LONG),
	]

DT_LEFT = 0x00000000
DT_CENTER = 0x00000001
DT_RIGHT = 0x00000002
DT_WORDBREAK = 0x00000010
DT_NOPREFIX = 0x00000800

def _render_gdi_mask(
	text: str,
	font_name: str,
	font_size: int,
	is_bold: bool,
	width: int,
	height: int,
	align: str,
	vertical_align: str
) -> Image.Image:
	gdi32 = ctypes.windll.gdi32
	user32 = ctypes.windll.user32

	hdc_screen = user32.GetDC(0)
	hdc = gdi32.CreateCompatibleDC(hdc_screen)
	user32.ReleaseDC(0, hdc_screen)
	
	bmi = BITMAPINFO()
	bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
	bmi.bmiHeader.biWidth = width
	bmi.bmiHeader.biHeight = -height
	bmi.bmiHeader.biPlanes = 1
	bmi.bmiHeader.biBitCount = 32
	bmi.bmiHeader.biCompression = 0

	pixels_ptr = ctypes.c_void_p()
	hbitmap = gdi32.CreateDIBSection(
		hdc, ctypes.byref(bmi), 0, ctypes.byref(pixels_ptr), None, 0
	)
	gdi32.SelectObject(hdc, hbitmap)

	gdi32.SetBkMode(hdc, 1)  # TRANSPARENT
	gdi32.SetTextColor(hdc, 0x00FFFFFF)

	hbrush = gdi32.CreateSolidBrush(0x00000000)
	rect = RECT(0, 0, width, height)
	user32.FillRect(hdc, ctypes.byref(rect), hbrush)
	gdi32.DeleteObject(hbrush)

	weight = 700 if is_bold else 400
	hfont = gdi32.CreateFontW(
		-font_size, 0, 0, 0, weight, 0, 0, 0,
		1,  # DEFAULT_CHARSET
		0, 0,
		4,  # ANTIALIASED_QUALITY
		0, font_name
	)
	gdi32.SelectObject(hdc, hfont)

	flags = DT_WORDBREAK | DT_NOPREFIX
	if align == "center":
		flags |= DT_CENTER
	elif align == "right":
		flags |= DT_RIGHT
	else:
		flags |= DT_LEFT

	# Compute vertical alignment using DT_CALCRECT
	rect_calc = RECT(0, 0, width, height)
	user32.DrawTextW(hdc, text, -1, ctypes.byref(rect_calc), flags | 0x00000400)
	calc_height = rect_calc.bottom - rect_calc.top

	if vertical_align == "middle":
		top_y = max(0, (height - calc_height) // 2)
	elif vertical_align == "bottom":
		top_y = max(0, height - calc_height)
	else:
		top_y = 0

	rect_draw = RECT(0, top_y, width, top_y + calc_height)
	user32.DrawTextW(hdc, text, -1, ctypes.byref(rect_draw), flags)

	buf = ctypes.string_at(pixels_ptr, width * height * 4)
	img_rgba = Image.frombuffer("RGBA", (width, height), buf, "raw", "BGRA", 0, 1)
	mask = img_rgba.convert("L")

	gdi32.DeleteObject(hfont)
	gdi32.DeleteObject(hbitmap)
	gdi32.DeleteDC(hdc)

	return mask

def _draw_text_gdi(
	draw: ImageDraw.ImageDraw,
	text: str,
	font_families: Sequence[str],
	font_size: int,
	is_bold: bool,
	color_hex: str,
	box: Mapping[str, Any],
	align: str,
	vertical_align: str,
	scripts: set[str]
) -> None:
	font_path = None
	for candidate in _font_candidate_paths(font_families, "bold" if is_bold else "regular", scripts):
		if candidate.exists():
			font_path = candidate
			break

	font_name = "Arial"
	added_font = False
	if font_path:
		font_name = font_path.stem
		# Clean weight variant suffix from family name
		for suffix in ["-Bold", "-Regular", "-SemiBold", "-Medium", " Bold", " Regular", " SemiBold", " Medium"]:
			if font_name.endswith(suffix):
				font_name = font_name[:-len(suffix)]
				break
		# If font file is local to project, register it temporarily in Windows GDI
		if "Windows" not in str(font_path):
			try:
				ctypes.windll.gdi32.AddFontResourceExW(str(font_path), 0x10, 0)
				added_font = True
			except Exception:
				pass

	try:
		x = int(box.get("x") or 0)
		y = int(box.get("y") or 0)
		width = int(box.get("width") or 0)
		height = int(box.get("height") or 0)

		mask = _render_gdi_mask(text, font_name, font_size, is_bold, width, height, align, vertical_align)
		solid = Image.new("RGBA", (width, height), color_hex)
		draw._image.paste(solid, (x, y), mask)
	finally:
		if added_font and font_path:
			try:
				ctypes.windll.gdi32.RemoveFontResourceExW(str(font_path), 0x10, 0)
			except Exception:
				pass


def _draw_text_layer(draw: ImageDraw.ImageDraw, layer: Mapping[str, Any], values: Mapping[str, Any]) -> None:
	box = layer.get("box") or {}
	style = layer.get("style") or {}
	placeholder = _normalize_text(layer.get("placeholder"))
	layer_id = _normalize_text(layer.get("id"))
	text = _normalize_text(values.get(layer_id))
	if not text and placeholder.startswith("{{") and placeholder.endswith("}}"):
		key = placeholder[2:-2].strip()
		text = _normalize_text(values.get(key))
	if not text:
		text = _normalize_text(values.get(layer_id, placeholder))

	if not text:
		return

	x = int(box.get("x") or 0)
	y = int(box.get("y") or 0)
	width = int(box.get("width") or 0)
	height = int(box.get("height") or 0)
	scripts = _detect_scripts(text)
	style_families = _extract_value_candidates(style)
	if scripts:
		font_families = _merge_font_families(_script_default_families(scripts), style_families + GLOBAL_FONT_FALLBACK)
	else:
		font_families = _merge_font_families(style_families, GLOBAL_FONT_FALLBACK)
	font = _fit_font_to_box(draw, text, box, style, font_families, scripts)
	lines = _wrap_text(draw, text, font, width)
	line_spacing = max(2, getattr(font, "size", 24) // 5)
	line_boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
	line_heights = [(bounds[3] - bounds[1]) for bounds in line_boxes]
	total_height = sum(line_heights) + line_spacing * max(0, len(lines) - 1)

	vertical_align = _normalize_text(style.get("vertical_align")).lower()
	if vertical_align == "bottom":
		current_y = y + height - total_height
	elif vertical_align == "middle":
		current_y = y + max(0, (height - total_height) // 2)
	else:
		current_y = y

	color = _normalize_text(style.get("color")) or "#000000"
	align = _normalize_text(style.get("align")).lower()
	stroke_width = 0
	is_bold = _is_bold_weight(style.get("font_weight"))

	import platform
	if platform.system() == "Windows" and scripts:
		_draw_text_gdi(draw, text, font_families, font.size, is_bold, color, box, align, vertical_align, scripts)
		return

	if is_bold:
		stroke_width = 1 if getattr(font, "size", 24) < 42 else 2

	for line, bounds in zip(lines, line_boxes):
		line_width = bounds[2] - bounds[0]
		if align == "right":
			current_x = x + max(0, width - line_width)
		elif align == "center":
			current_x = x + max(0, (width - line_width) // 2)
		else:
			current_x = x
		draw.text((current_x, current_y), line, font=font, fill=color, stroke_width=stroke_width, stroke_fill=color)
		current_y += (bounds[3] - bounds[1]) + line_spacing


def _draw_image_layer(
	image: Image.Image,
	layer: Mapping[str, Any],
	values: Mapping[str, Any],
	uploaded_image_path: str | Path | None = None
) -> None:
	box = layer.get("box") or {}
	layer_id = _normalize_text(layer.get("id"))

	photo_image = None
	img_data = values.get(layer_id)

	if isinstance(img_data, bytes):
		import io
		try:
			photo_image = Image.open(io.BytesIO(img_data)).convert("RGBA")
		except Exception:
			pass
	elif uploaded_image_path:
		resolved_path = _resolve_path(uploaded_image_path)
		if resolved_path.exists():
			try:
				photo_image = Image.open(resolved_path).convert("RGBA")
			except Exception:
				pass

	if not photo_image:
		return

	x = int(box.get("x") or 0)
	y = int(box.get("y") or 0)
	width = int(box.get("width") or 0)
	height = int(box.get("height") or 0)

	if width > 0 and height > 0:
		photo_image = photo_image.resize((width, height), Image.LANCZOS)
		image.paste(photo_image, (x, y), photo_image)



def render_overlay(
	overlay: Mapping[str, Any],
	values: Mapping[str, Any] | None = None,
	uploaded_image_path: str | Path | None = None
) -> Image.Image:
	resolved_values = values or {}
	image = _load_base_image(overlay)
	draw = ImageDraw.Draw(image)

	for layer in overlay.get("overlay_layers") or []:
		if not isinstance(layer, Mapping):
			continue
		layer_type = _normalize_text(layer.get("type")).lower()
		if layer_type == "text":
			_draw_text_layer(draw, layer, resolved_values)
		elif layer_type == "image":
			_draw_image_layer(image, layer, resolved_values, uploaded_image_path)

	return image


def render_overlay_file(
	overlay_path: str | Path,
	values: Mapping[str, Any] | None = None,
	output_path: str | Path | None = None,
) -> Path | Image.Image:
	overlay = load_overlay_json(overlay_path)
	image = render_overlay(overlay, values=values)

	if output_path is None:
		return image

	resolved_output_path = _resolve_path(output_path)
	resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
	image.save(resolved_output_path)
	return resolved_output_path


def render_poster(
	template: Mapping[str, Any],
	values: Mapping[str, Any] | None,
	output_path: str | Path,
	uploaded_image_path: str | Path | None = None,
) -> Path:
	"""Compatibility wrapper used by the FastAPI generate route."""
	image = render_overlay(template, values=values, uploaded_image_path=uploaded_image_path)
	resolved_output_path = _resolve_path(output_path)
	resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
	image.save(resolved_output_path)
	return resolved_output_path


def _parse_values(raw_values: Sequence[str]) -> Dict[str, str]:
	parsed: Dict[str, str] = {}
	for item in raw_values:
		if "=" not in item:
			raise ValueError(f"Invalid value assignment: {item!r}. Expected key=value.")
		key, value = item.split("=", 1)
		parsed[key.strip()] = value.strip()
	return parsed


def build_arg_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Render an overlay.json template without RAG or indexing.")
	parser.add_argument("overlay", help="Path to overlay.json")
	parser.add_argument("--output", help="Where to write the rendered image")
	parser.add_argument(
		"--value",
		action="append",
		default=[],
		dest="values",
		help="Field assignment in the form key=value. Repeat for multiple values.",
	)
	parser.add_argument(
		"--values-json",
		help="JSON object containing field values. Merged with --value entries.",
	)
	return parser


def main(argv: Sequence[str] | None = None) -> int:
	parser = build_arg_parser()
	args = parser.parse_args(argv)
	values: Dict[str, Any] = {}

	if args.values_json:
		values.update(json.loads(args.values_json))
	values.update(_parse_values(args.values))

	result = render_overlay_file(args.overlay, values=values, output_path=args.output)
	if isinstance(result, Path):
		print(result)
	else:
		print("Rendered image in memory")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
