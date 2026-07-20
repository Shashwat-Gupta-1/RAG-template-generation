import streamlit as st
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from auth_utils import auth_gate
from history_utils import render_history_sidebar

# pyrefly: ignore [missing-import]
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from typing import List, Dict, Any, Optional

st.set_page_config(page_title="Add Your Template", layout="wide")

# Run Auth Gate
if not auth_gate():
    st.stop()

# Render History Sidebar
render_history_sidebar()

def get_existing_categories() -> List[str]:
    """Scans templates/ directory for subdirectories."""
    templates_dir = "templates"
    if not os.path.exists(templates_dir):
        return []
    try:
        return sorted([
            name for name in os.listdir(templates_dir)
            if os.path.isdir(os.path.join(templates_dir, name))
        ])
    except Exception:
        return []


def validate_subfolder_name(subfolder_name: str, category_name: str) -> Optional[str]:
    """Validates that the subfolder name does not conflict with existing templates category folder names."""
    name = subfolder_name.strip().lower()
    cat = category_name.strip().lower()
    
    if not name:
        return "Subfolder/Template ID cannot be empty."
        
    if name == cat:
        return f"Subfolder/Template ID '{subfolder_name}' cannot be the same as the category folder name '{category_name}'."
        
    templates_dir = "templates"
    if os.path.exists(templates_dir):
        try:
            existing_folders = [
                f.lower() for f in os.listdir(templates_dir)
                if os.path.isdir(os.path.join(templates_dir, f))
            ]
            if name in existing_folders:
                return f"Subfolder name '{subfolder_name}' conflicts with an existing templates category folder name '{name}'."
        except Exception:
            pass
            
    return None


st.title("Add your own template")
st.caption(
    "Upload your designed PNG, draw placeholder boxes, configure each field, "
    "and save. Your template becomes searchable immediately."
)

for key, default in [
    ("at_png_bytes", None),
    ("at_img_w", 0),
    ("at_img_h", 0),
    ("at_field_configs", {}),
    ("at_overlay", None),
    ("at_step", "upload"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

STEPS = {
    "upload": "1. Upload PNG",
    "zone_map": "2. Draw boxes",
    "save": "3. Save"
}
st.write(
    " → ".join(
        f"**{v}**" if k == st.session_state.at_step else v
        for k, v in STEPS.items()
    )
)
st.divider()

# ── STEP 1: Upload ─────────────────────────────────────────────────────
if st.session_state.at_step == "upload":
    uploaded = st.file_uploader(
        "Upload your template PNG",
        type=["png", "jpg", "jpeg"]
    )
    if uploaded:
        png_bytes = uploaded.read()
        img = Image.open(io.BytesIO(png_bytes))
        st.session_state.at_png_bytes = png_bytes
        st.session_state.at_img_w = img.size[0]
        st.session_state.at_img_h = img.size[1]
        st.image(
            png_bytes,
            caption=f"{img.size[0]} × {img.size[1]} px"
        )
        if st.button("Continue — draw boxes →", type="primary"):
            st.session_state.at_step = "zone_map"
            st.rerun()

# ── STEP 2: Zone mapper ────────────────────────────────────────────────
elif st.session_state.at_step == "zone_map":
    st.subheader("Draw placeholder boxes")
    st.caption(
        "Drag to draw a rectangle for each text or image field."
    )

    img_w = st.session_state.at_img_w
    img_h = st.session_state.at_img_h
    DISPLAY_W = 680
    display_h = int(img_h * (DISPLAY_W / img_w))
    img = Image.open(io.BytesIO(st.session_state.at_png_bytes))

    canvas_result = st_canvas(
        background_image=img,
        drawing_mode="rect",
        stroke_width=2,
        stroke_color="#F7834F",
        fill_color="rgba(247,131,79,0.15)",
        height=display_h,
        width=DISPLAY_W,
        key="at_canvas"
    )

    objects = []
    if canvas_result.json_data:
        objects = canvas_result.json_data.get("objects", [])

    if not objects:
        st.info("Draw at least one box on the image.")
    else:
        st.write(f"**{len(objects)} box(es).** Configure each:")
        field_configs = {}

        for i, obj in enumerate(objects):
            with st.expander(f"Field {i + 1}", expanded=(i == 0)):
                c1, c2 = st.columns(2)
                with c1:
                    fid = st.text_input(
                        "Field ID",
                        value=f"field_{i + 1}",
                        key=f"at_fid_{i}"
                    )
                    ftype = st.selectbox(
                        "Type", ["text", "image"],
                        key=f"at_ftype_{i}"
                    )
                    instruction = st.text_input(
                        "AI instruction",
                        value=f"Value for {fid}",
                        key=f"at_finstr_{i}"
                    )
                    llm = st.checkbox(
                        "AI can generate if missing",
                        False,
                        key=f"at_llm_{i}"
                    )
                with c2:
                    if ftype == "text":
                        ff = st.selectbox(
                            "Font",
                            ["Poppins", "NotoSans", "NotoSansDevanagari"],
                            key=f"at_ff_{i}"
                        )
                        fs = st.number_input(
                            "Size", 8, 200, 48,
                            key=f"at_fs_{i}"
                        )
                        fsm = st.number_input(
                            "Min size", 6, 100, 20,
                            key=f"at_fsm_{i}"
                        )
                        fw = st.selectbox(
                            "Weight",
                            ["bold", "normal", "semibold"],
                            key=f"at_fw_{i}"
                        )
                        fc = st.color_picker(
                            "Color", "#FFFFFF",
                            key=f"at_fc_{i}"
                        )
                        fa = st.selectbox(
                            "Align",
                            ["center", "left", "right"],
                            key=f"at_fa_{i}"
                        )
                        field_configs[str(i)] = {
                            "id": fid, "type": ftype,
                            "instruction": instruction,
                            "llm_can_invent": llm,
                            "font_family": ff,
                            "font_size": fs,
                            "font_size_min": fsm,
                            "font_weight": fw,
                            "color": fc,
                            "align": fa
                        }
                    else:
                        shape = st.selectbox(
                            "Shape",
                            ["circle", "rectangle"],
                            key=f"at_sh_{i}"
                        )
                        bc = st.color_picker(
                            "Border color", "#FFFFFF",
                            key=f"at_bc_{i}"
                        )
                        bw = st.number_input(
                            "Border width", 0, 20, 4,
                            key=f"at_bw_{i}"
                        )
                        field_configs[str(i)] = {
                            "id": fid, "type": ftype,
                            "instruction": instruction,
                            "llm_can_invent": False,
                            "shape": shape,
                            "border_color": bc,
                            "border_width": bw
                        }

        st.session_state.at_field_configs = field_configs

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Back"):
                st.session_state.at_step = "upload"
                st.rerun()
        with c2:
            if st.button("Continue to save →", type="primary"):
                from phase2.zone_mapper import (
                    canvas_objects_to_overlay_layers,
                    validate_layers
                )
                layers = canvas_objects_to_overlay_layers(
                    objects, field_configs,
                    img_w, img_h, DISPLAY_W, display_h
                )
                errors = validate_layers(layers, img_w, img_h)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    st.session_state.at_overlay = {
                        "overlay_layers": layers,
                        "canvas": {"width": img_w, "height": img_h}
                    }
                    st.session_state.at_step = "save"
                    st.rerun()

# ── STEP 3: Save ──────────────────────────────────────────────────────
elif st.session_state.at_step == "save":
    st.subheader("Save your template")
    overlay = st.session_state.at_overlay
    field_ids = [
        l["id"] for l in overlay.get("overlay_layers", [])
        if l["type"] == "text"
    ]
    instructions = [
        l["instruction"] for l in overlay.get("overlay_layers", [])
        if l["type"] == "text"
    ]

    existing_categories = get_existing_categories()
    cat_options = existing_categories + ["Create new folder..."]
    selected_cat = st.selectbox(
        "Category folder",
        options=cat_options,
        help="Select an existing templates category folder or create a new one"
    )
    
    if selected_cat == "Create new folder...":
        category = st.text_input(
            "Enter new category folder name",
            placeholder="holi",
            help="Lowercase, underscores only, no spaces"
        ).strip().lower()
    else:
        category = selected_cat.strip()

    base_id = st.text_input(
        "Subfolder/Template base ID",
        placeholder="holi",
        help="Cannot match the category folder name or any other templates category folder name. System adds sequence number if name already exists"
    )
    hint = st.text_area(
        "Brief description for search",
        placeholder="Holi festival greeting poster with employee name",
        height=70
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Back to boxes"):
            st.session_state.at_step = "zone_map"
            st.rerun()
    with c2:
        if st.button("Generate tags and save", type="primary"):
            validation_error = validate_subfolder_name(base_id, category)
            if not category or not base_id.strip():
                st.error("Category and subfolder/template ID are required.")
            elif validation_error:
                st.error(validation_error)
            else:
                with st.spinner("Generating tags and saving..."):
                    from processing.llm import generate_tags_and_description
                    meta = generate_tags_and_description(
                        category.strip(), field_ids,
                        instructions, hint.strip()
                    )

                    full_overlay = {
                        "template_id": base_id.strip(),
                        "description": meta["description"],
                        "type": "poster",
                        "tags": meta["tags"],
                        "base_image": "",
                        "canvas": overlay["canvas"],
                        "overlay_layers": overlay["overlay_layers"]
                    }

                    from phase2.template_saver import save_template_files
                    try:
                        _, resolved_id = save_template_files(
                            st.session_state.at_png_bytes,
                            full_overlay,
                            category.strip(),
                            base_id.strip()
                        )
                        st.success(
                            f"Saved as `{resolved_id}` in "
                            f"`{category.strip()}/` — "
                            f"searchable immediately!"
                        )
                        st.balloons()
                        for k in [
                            "at_png_bytes", "at_img_w", "at_img_h",
                            "at_field_configs", "at_overlay"
                        ]:
                            st.session_state[k] = (
                                None if k in ("at_png_bytes", "at_overlay")
                                else (0 if "img" in k else {})
                            )
                        st.session_state.at_step = "upload"
                    except Exception as e:
                        st.error(f"Save failed: {e}")