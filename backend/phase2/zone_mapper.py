def canvas_objects_to_overlay_layers(
    canvas_objects: list[dict],
    field_configs: dict[str, dict],
    img_width: int,
    img_height: int,
    display_width: int,
    display_height: int
) -> list[dict]:
    """
    Converts streamlit-drawable-canvas rectangles to overlay_layers.
    Scales display coordinates to actual PNG pixels.
    """
    scale_x = img_width / display_width
    scale_y = img_height / display_height
    layers = []

    for i, obj in enumerate(canvas_objects):
        if obj.get("type") != "rect":
            continue

        cfg = field_configs.get(str(i), {})
        field_id = (
            cfg.get("id", f"field_{i + 1}")
            .strip()
            .replace(" ", "_")
            .lower()
        )
        field_type = cfg.get("type", "text")

        box = {
            "x": max(0, round(obj["left"] * scale_x)),
            "y": max(0, round(obj["top"] * scale_y)),
            "width": round(obj["width"] * scale_x),
            "height": round(obj["height"] * scale_y),
        }

        if field_type == "text":
            layer = {
                "id": field_id,
                "type": "text",
                "placeholder": f"{{{{{field_id}}}}}",
                "instruction": cfg.get(
                    "instruction", f"Value for {field_id}"
                ),
                "llm_can_invent": cfg.get("llm_can_invent", False),
                "box": box,
                "style": {
                    "font_family": cfg.get("font_family", "Poppins"),
                    "font_size": int(cfg.get("font_size", 48)),
                    "font_size_min": int(cfg.get("font_size_min", 20)),
                    "font_weight": cfg.get("font_weight", "bold"),
                    "font_style": cfg.get("font_style", "normal"),
                    "color": cfg.get("color", "#FFFFFF"),
                    "align": cfg.get("align", "center"),
                    "vertical_align": "middle",
                },
                "editable": True,
            }
        else:
            layer = {
                "id": field_id,
                "type": "image",
                "placeholder": f"{{{{{field_id}}}}}",
                "instruction": cfg.get(
                    "instruction", "Upload image to place here"
                ),
                "llm_can_invent": False,
                "box": box,
                "style": {
                    "shape": cfg.get("shape", "circle"),
                    "border_color": cfg.get("border_color", "#FFFFFF"),
                    "border_width": int(cfg.get("border_width", 4)),
                },
                "editable": True,
            }

        layers.append(layer)

    return layers


def validate_layers(
    layers: list[dict],
    canvas_w: int,
    canvas_h: int
) -> list[str]:
    """Returns list of error strings. Empty = all good."""
    errors = []
    ids_seen = set()

    for i, layer in enumerate(layers):
        fid = layer.get("id", "")

        if not fid:
            errors.append(f"Box {i + 1} has no field ID")
        elif fid in ids_seen:
            errors.append(f"Duplicate field ID: '{fid}'")
        else:
            ids_seen.add(fid)

        box = layer.get("box", {})
        if box.get("width", 0) < 20 or box.get("height", 0) < 10:
            errors.append(
                f"Field '{fid}' box is too small — "
                f"draw a larger rectangle"
            )

        if box.get("x", 0) + box.get("width", 0) > canvas_w:
            errors.append(
                f"Field '{fid}' extends past right edge of image"
            )
        if box.get("y", 0) + box.get("height", 0) > canvas_h:
            errors.append(
                f"Field '{fid}' extends past bottom edge of image"
            )

        if layer.get("type") == "text":
            s = layer.get("style", {})
            if s.get("font_size_min", 999) >= s.get("font_size", 0):
                errors.append(
                    f"Field '{fid}': min font size must be "
                    f"smaller than font size"
                )

    return errors