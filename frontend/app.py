import time
import json
import base64
# pyrefly: ignore [missing-import]
import streamlit as st
import requests

API = "http://localhost:8000"

import streamlit.components.v1 as components
import os

st.set_page_config(
    page_title="MS Fincap Template Generator",
    layout="centered"
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 2px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        font-size: 0.95rem;
        padding: 8px 20px;
        border-radius: 8px 8px 0 0;
    }

    /* Card-like sections */
    .block-container { padding-top: 2rem; }

    /* Progress bar label */
    .progress-label {
        font-size: 0.85rem;
        color: #64748b;
        margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)

st.title("MS Fincap Template Generator")
st.caption("Generate personalised posters - one at a time or in bulk from an Excel sheet.")

# ── Session state init ────────────────────────────────────────────────────────
defaults = {
    "selected_folder": None,
    "selected_template_id": None,
    "extra_fields": {},
    # Bulk state
    "bulk_job_id": None,
    "bulk_total": 0,
    "bulk_done": False,
    "bulk_error": None,
    "bulk_download_url": None,
    "bulk_preview": None,
    "bulk_file_data": None,
    "bulk_photo_data": None,
    "bulk_prompt_data": None,
    "bulk_style_overrides": {},
    "single_started": False,
    "bulk_started": False,
    "single_layout_overrides": {},
    "bulk_layout_overrides": {},
    "single_style_overrides": {},
    "fields_submitted": False,       # True once user clicks Submit on needs_input form
    "pending_missing_fields": [],    # The list of fields we are waiting on
    "bulk_column_mapping": {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
#  TAB LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
tab_single, tab_bulk = st.tabs(["Single Poster", "Bulk Generate (Excel)"])


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Single Poster (original flow, unchanged)
# ══════════════════════════════════════════════════════════════════════════════
with tab_single:
    st.subheader("Generate a single poster")

    # Helper: Reset single poster state
    def _reset_single():
        st.session_state.selected_folder = None
        st.session_state.selected_template_id = None
        st.session_state.single_started = False
        st.session_state.fields_submitted = False
        st.session_state.pending_missing_fields = []
        st.session_state.single_layout_overrides = {}
        st.session_state.single_style_overrides = {}
        for k in list(st.session_state.keys()):
            if k.startswith("field_"):
                del st.session_state[k]

    # 1. Main Inputs - Full Width
    prompt = st.text_area(
        "What poster do you need?",
        placeholder="Holi poster for Rahul Kumar",
        height=80,
        key="single_prompt",
    )

    photo = st.file_uploader(
        "Upload profile photo (optional)",
        type=["jpg", "jpeg", "png", "heic"],
        key="single_photo",
    )

    # 2. Design Selection and Live Preview section (Vertical Flow)
    if st.session_state.single_started:
        if prompt.strip():
            # ── Guard: if we are waiting for user to fill fields, don't auto-call backend ──
            if st.session_state.pending_missing_fields:
                st.write("**Please fill in the poster details:**")
                for fid in st.session_state.pending_missing_fields:
                    st.text_input(
                        fid.replace("_", " ").title(),
                        placeholder=f"Enter {fid}",
                        key=f"field_{fid}",
                    )
                all_filled = all(
                    bool(str(st.session_state.get(f"field_{fid}", "")).strip())
                    for fid in st.session_state.pending_missing_fields
                )
                if not st.session_state.fields_submitted:
                    submit_btn = st.button(
                        "Generate Poster",
                        type="primary",
                        disabled=not all_filled,
                        key="btn_submit_fields",
                    )
                    if not all_filled:
                        st.caption("Fill in all fields above to enable the Generate button.")
                    if submit_btn:
                        st.session_state.fields_submitted = True
                        st.rerun()

            # Only call backend when: no pending fields OR fields have been submitted
            if not st.session_state.pending_missing_fields or st.session_state.fields_submitted:
                # Sync slider state values dynamically (layout and styling)
                for key in list(st.session_state.keys()):
                    # Layout overrides sync
                    if key.startswith("sx_"):
                        lid = key.replace("sx_", "")
                        x_val = st.session_state[key]
                        y_val = st.session_state.get(f"sy_{lid}", 0)
                        current_override = st.session_state.single_layout_overrides.setdefault(lid, {})
                        current_override["x"] = x_val
                        current_override["y"] = y_val

                    # Style overrides sync
                    elif key.startswith("sfont_"):
                        lid = key.replace("sfont_", "")
                        font_family = st.session_state[key]
                        font_weight = st.session_state.get(f"sweight_{lid}", "(Template default)")
                        use_size = st.session_state.get(f"suse_size_{lid}", False)
                        size_val = st.session_state.get(f"ssize_{lid}", 48)
                        use_color = st.session_state.get(f"suse_color_{lid}", False)
                        color_val = st.session_state.get(f"scolor_{lid}", "#FFFFFF")

                        layer_style = st.session_state.single_style_overrides.setdefault(lid, {})
                        if font_family != "(Template default)":
                            layer_style["font_family"] = font_family
                        else:
                            layer_style.pop("font_family", None)

                        if font_weight == "Bold":
                            layer_style["font_weight"] = "bold"
                        elif font_weight == "Normal":
                            layer_style["font_weight"] = "regular"
                        else:
                            layer_style.pop("font_weight", None)

                        if use_size:
                            layer_style["font_size"] = size_val
                        else:
                            layer_style.pop("font_size", None)

                        if use_color:
                            layer_style["color"] = color_val
                        else:
                            layer_style.pop("color", None)

                        # If all overrides for this layer are empty, clean up the layer dict
                        if not layer_style:
                            st.session_state.single_style_overrides.pop(lid, None)

                # Gather base values to hit endpoint and fetch preview or needs_input
                data = {
                    "prompt": prompt.strip(),
                    "folder": st.session_state.selected_folder or "",
                    "template_id": st.session_state.selected_template_id or "",
                }
                if st.session_state.single_style_overrides:
                    data["style_overrides"] = json.dumps(st.session_state.single_style_overrides)

                if st.session_state.single_layout_overrides:
                    data["layout_overrides"] = json.dumps(st.session_state.single_layout_overrides)

                # Gather dynamically entered input fields
                for key in list(st.session_state.keys()):
                    if key.startswith("field_"):
                        field_id = key.replace("field_", "")
                        data[field_id] = st.session_state[key]

                files = {}
                if photo:
                    files["image"] = (photo.name, photo.getvalue(), photo.type)

                spinner_msg = (
                    "Generating preview…"
                    if st.session_state.selected_template_id
                    else "Finding the right template…"
                )

                try:
                    with st.spinner(spinner_msg):
                        res = requests.post(
                            f"{API}/generate?json=true",
                            data=data,
                            files=files or None,
                            headers={"Accept": "application/json"},
                            timeout=30,
                        )
                    
                except Exception as exc:
                    st.error(f"Could not connect to backend: {exc}")
                    res = None
                
                if res is not None:
                    resp = res.json()
                    status = resp.get("status")

                    if status == "success":
                        # Show preview + draggable editor
                        st.subheader("Live Preview")
                        
                        img_bytes = base64.b64decode(resp["image"])
                        canvas = resp.get("canvas") or {"width": 1024, "height": 1536}
                        layers = resp.get("overlay_layers") or []

                        # Show the poster image
                        st.image(img_bytes, use_column_width=True)

                        # Draggable position & styling editor expander
                        if layers:
                            with st.expander("Adjust Placeholder Positions & Styling (click to expand)", expanded=False):
                                st.caption("Drag sliders to reposition text/image zones and customize fonts per placeholder. Changes update dynamically.")
                                canvas_w = canvas.get("width", 1024)
                                canvas_h = canvas.get("height", 1536)

                                FONT_OPTIONS = [
                                    "(Template default)",
                                    "Poppins",
                                    "NotoSans",
                                    "Arial",
                                    "Times New Roman",
                                    "Georgia",
                                    "Calibri",
                                    "Verdana",
                                    "Trebuchet MS",
                                ]
                                
                                for layer in layers:
                                    lid = layer.get("id")
                                    box = layer.get("box")
                                    if not lid or not box:
                                        continue
                                    
                                    st.markdown(f"#### **Placeholder: {lid}**")
                                    
                                    # Layout controls
                                    current_layout = st.session_state.single_layout_overrides.get(lid, box)
                                    c1, c2 = st.columns(2)
                                    c1.slider(f"X position ({lid})", 0, canvas_w, int(current_layout.get("x", box["x"])), key=f"sx_{lid}")
                                    c2.slider(f"Y position ({lid})", 0, canvas_h, int(current_layout.get("y", box["y"])), key=f"sy_{lid}")
                                    
                                    # If it's a text layer, render font styling overrides
                                    ltype = str(layer.get("type", "")).lower()
                                    if ltype == "text":
                                        current_style = st.session_state.single_style_overrides.get(lid, {})
                                        style = layer.get("style", {})

                                        # 1. Font Family & Weight
                                        cs1, cs2 = st.columns(2)
                                        
                                        current_font = current_style.get("font_family", "(Template default)")
                                        font_idx = 0
                                        if current_font in FONT_OPTIONS:
                                            font_idx = FONT_OPTIONS.index(current_font)
                                            
                                        cs1.selectbox(
                                            f"Font family ({lid})",
                                            options=FONT_OPTIONS,
                                            index=font_idx,
                                            key=f"sfont_{lid}"
                                        )
                                        
                                        current_weight = current_style.get("font_weight", "regular")
                                        weight_val = "(Template default)"
                                        if current_weight == "bold":
                                            weight_val = "Bold"
                                        elif current_weight == "regular":
                                            weight_val = "Normal"
                                            
                                        cs2.radio(
                                            f"Font weight ({lid})",
                                            options=["(Template default)", "Bold", "Normal"],
                                            index=["(Template default)", "Bold", "Normal"].index(weight_val),
                                            horizontal=True,
                                            key=f"sweight_{lid}"
                                        )

                                        # 2. Font Size & Text Color
                                        cs3, cs4 = st.columns(2)
                                        
                                        size_overridden = "font_size" in current_style
                                        use_size = cs3.checkbox(f"Override font size ({lid})", value=size_overridden, key=f"suse_size_{lid}")
                                        cs3.slider(
                                            f"Font size (px) ({lid})",
                                            min_value=12,
                                            max_value=96,
                                            value=int(current_style.get("font_size", style.get("font_size", 48))),
                                            step=2,
                                            disabled=not use_size,
                                            key=f"ssize_{lid}"
                                        )

                                        color_overridden = "color" in current_style
                                        use_color = cs4.checkbox(f"Override text colour ({lid})", value=color_overridden, key=f"suse_color_{lid}")
                                        cs4.color_picker(
                                            f"Text colour ({lid})",
                                            value=current_style.get("color", style.get("color", "#FFFFFF")),
                                            disabled=not use_color,
                                            key=f"scolor_{lid}"
                                        )
                                    
                                    st.markdown("---")

                        col_dl, col_reset = st.columns([3, 1])
                        with col_dl:
                            st.download_button(
                                label="Download Poster",
                                data=img_bytes,
                                file_name=f"poster_{st.session_state.selected_template_id or 'generated'}.png",
                                mime="image/png",
                                type="primary",
                                use_container_width=True,
                            )
                        with col_reset:
                            if st.button("Start Over", type="secondary", use_container_width=True):
                                _reset_single()
                                st.rerun()
                    else:

                        if status == "no_match":
                            st.error("No matching template found.")
                            if st.button("Start Over", type="secondary"):
                                _reset_single()
                                st.rerun()
                        
                        elif status == "ambiguous":
                            st.warning("Which category did you mean?")
                            for m in resp["matches"]:
                                if st.button(m["display_name"], key=f"cat_{m['folder']}"):
                                    st.session_state.selected_folder = m["folder"]
                                    st.rerun()

                        elif status == "gallery":
                            st.info(f"Select a design for **{resp['display_name']}**:")
                            for t in resp["templates"]:
                                with st.container():
                                    st.markdown("---")
                                    col_info, col_img = st.columns([3, 2])
                                    with col_info:
                                        st.subheader(t["template_id"])
                                        st.write(t["description"])
                                        if st.button("Use this Design", key=f"tmpl_{t['template_id']}", type="primary"):
                                            st.session_state.selected_folder = resp["folder"]
                                            st.session_state.selected_template_id = t["template_id"]
                                            st.rerun()
                                    with col_img:
                                        base_img = t.get("base_image")
                                        if base_img and os.path.exists(base_img):
                                            st.image(base_img, caption=f"Preview: {t['template_id']}", use_column_width=True)

                        elif status == "needs_input":
                            # Save the missing fields list and template info in session state
                            # so we can show the form WITHOUT calling the backend again
                            st.session_state.pending_missing_fields = resp["missing_fields"]
                            st.session_state.selected_folder = resp.get("folder")
                            st.session_state.selected_template_id = resp.get("template_id")
                            st.session_state.fields_submitted = False
                            st.rerun()  # Rerun so the guard above takes over and shows the form
        else:
            st.warning("Please describe what you need.")
            st.session_state.single_started = False
            st.rerun()
    else:
        # Show Generate Poster button to start the process
        if st.button("Generate poster", type="primary", use_container_width=True, key="btn_single_generate"):
            if not prompt.strip():
                st.warning("Please describe what you need.")
            else:
                st.session_state.single_started = True
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Bulk Generate (Excel)
# ══════════════════════════════════════════════════════════════════════════════
with tab_bulk:
    st.subheader("Bulk poster generation from Excel")
    st.markdown(
        "Upload an Excel sheet with one employee per row. "
        "The system will generate a personalised poster for every row and deliver them in a **ZIP file**."
    )

    # ── Helper: reset bulk state ───────────────────────────────────────────
    def _reset_bulk():
        st.session_state.bulk_job_id = None
        st.session_state.bulk_total = 0
        st.session_state.bulk_done = False
        st.session_state.bulk_error = None
        st.session_state.bulk_download_url = None
        st.session_state.bulk_preview = None
        st.session_state.bulk_file_data = None
        st.session_state.bulk_photo_data = None
        st.session_state.bulk_prompt_data = None
        st.session_state.bulk_style_overrides = {}
        st.session_state.bulk_layout_overrides = {}
        st.session_state.bulk_column_mapping = {}
        st.session_state.bulk_started = False

    # ── Step 1: Input / Preview stage (shown when no job is running) ───────
    if not st.session_state.bulk_job_id:
        
        # We always render the form inputs so the user can change them dynamically
        bulk_prompt = st.text_area(
            "Describe the poster type",
            placeholder="e.g. Holi poster, Eid greetings, Hiring announcement…",
            height=80,
            help="This tells the system which template to use.",
            key="bulk_prompt",
        )

        bulk_excel = st.file_uploader(
            "Upload Excel file (.xlsx)",
            type=["xlsx", "xls"],
            help="Must contain an 'emp_id' column plus fields required by the template.",
            key="bulk_excel",
        )

        excel_columns = []
        if bulk_excel is not None:
            try:
                import pandas as pd
                df_cols = pd.read_excel(bulk_excel, nrows=0)
                excel_columns = list(df_cols.columns)
            except Exception as e:
                st.error(f"Error reading Excel columns: {e}")

        bulk_photo = st.file_uploader(
            "Upload shared profile photo (optional)",
            type=["jpg", "jpeg", "png", "heic"],
            help="Used for templates with an image zone. Same photo applied to every poster.",
            key="bulk_photo",
        )

        if st.session_state.bulk_started:
            if not bulk_prompt.strip() or bulk_excel is None:
                st.warning("Please fill in the poster description and upload an Excel file.")
                st.session_state.bulk_started = False
                st.rerun()
            else:
                # Sync bulk slider state values dynamically (layout and styling)
                for key in list(st.session_state.keys()):
                    # Layout overrides
                    if key.startswith("bsx_"):
                        lid = key.replace("bsx_", "")
                        x_val = st.session_state[key]
                        y_val = st.session_state.get(f"bsy_{lid}", 0)
                        current_override = st.session_state.bulk_layout_overrides.setdefault(lid, {})
                        current_override["x"] = x_val
                        current_override["y"] = y_val

                    # Column mapping overrides
                    elif key.startswith("bmap_"):
                        fid = key.replace("bmap_", "")
                        col_val = st.session_state[key]
                        if col_val and col_val != "(Choose column...)":
                            st.session_state.bulk_column_mapping[fid] = col_val
                        else:
                            st.session_state.bulk_column_mapping.pop(fid, None)

                    # Style overrides
                    elif key.startswith("bfont_"):
                        lid = key.replace("bfont_", "")
                        font_family = st.session_state[key]
                        font_weight = st.session_state.get(f"bweight_{lid}", "(Template default)")
                        use_size = st.session_state.get(f"buse_size_{lid}", False)
                        size_val = st.session_state.get(f"bsize_{lid}", 48)
                        use_color = st.session_state.get(f"buse_color_{lid}", False)
                        color_val = st.session_state.get(f"bcolor_{lid}", "#FFFFFF")

                        layer_style = st.session_state.bulk_style_overrides.setdefault(lid, {})
                        if font_family != "(Template default)":
                            layer_style["font_family"] = font_family
                        else:
                            layer_style.pop("font_family", None)

                        if font_weight == "Bold":
                            layer_style["font_weight"] = "bold"
                        elif font_weight == "Normal":
                            layer_style["font_weight"] = "regular"
                        else:
                            layer_style.pop("font_weight", None)

                        if use_size:
                            layer_style["font_size"] = size_val
                        else:
                            layer_style.pop("font_size", None)

                        if use_color:
                            layer_style["color"] = color_val
                        else:
                            layer_style.pop("color", None)

                        # Clean up if empty
                        if not layer_style:
                            st.session_state.bulk_style_overrides.pop(lid, None)

                # Call /bulk/preview dynamically
                excel_bytes = bulk_excel.getvalue()
                files = {
                    "excel_file": (
                        bulk_excel.name,
                        excel_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                }
                if bulk_photo:
                    files["photo"] = (bulk_photo.name, bulk_photo.getvalue(), bulk_photo.type)

                data = {"prompt": bulk_prompt.strip()}
                if st.session_state.bulk_style_overrides:
                    data["style_overrides"] = json.dumps(st.session_state.bulk_style_overrides)
                if st.session_state.bulk_layout_overrides:
                    data["layout_overrides"] = json.dumps(st.session_state.bulk_layout_overrides)
                if st.session_state.bulk_column_mapping:
                    data["column_mapping"] = json.dumps(st.session_state.bulk_column_mapping)

                try:
                    with st.spinner("Generating preview of the first row…"):
                        res = requests.post(
                            f"{API}/bulk/preview",
                            data=data,
                            files=files,
                            timeout=30,
                        )
                    body = res.json()

                    if res.status_code == 200 and "preview_image" in body:
                        st.subheader("Live Preview")
                        
                        img_bytes = base64.b64decode(body["preview_image"])
                        canvas = body.get("canvas") or {"width": 1024, "height": 1536}
                        layers = body.get("overlay_layers") or []
                        
                        st.image(img_bytes, use_column_width=True)

                        if layers:
                            # Column Mapper Expander
                            with st.expander("Review & Adjust Column Mapping", expanded=True):
                                st.write("Debug layers:", layers)
                                st.caption("Choose which Excel column maps to each template placeholder. Changes update the preview dynamically.")
                                backend_col_map = body.get("column_map") or {}
                                for layer in layers:
                                    lid = layer.get("id")
                                    ltype = str(layer.get("type", "")).lower()
                                    can_invent = bool(layer.get("llm_can_invent", False))
                                    if not lid or ltype == "image" or can_invent:
                                        continue
                                    
                                    current_mapped_col = st.session_state.bulk_column_mapping.get(lid)
                                    if not current_mapped_col:
                                        current_mapped_col = backend_col_map.get(lid, "")
                                    
                                    options = ["(Choose column...)"] + excel_columns
                                    default_idx = 0
                                    if current_mapped_col in excel_columns:
                                        default_idx = options.index(current_mapped_col)
                                    
                                    st.selectbox(
                                        f"Field: **{lid}**",
                                        options=options,
                                        index=default_idx,
                                        key=f"bmap_{lid}"
                                    )

                            with st.expander("Adjust Placeholder Positions & Styling (click to expand)", expanded=False):
                                st.caption("Drag sliders to reposition text/image zones and customize fonts per placeholder. Changes update dynamically.")
                                canvas_w = canvas.get("width", 1024)
                                canvas_h = canvas.get("height", 1536)

                                FONT_OPTIONS = [
                                    "(Template default)",
                                    "Poppins",
                                    "NotoSans",
                                    "Arial",
                                    "Times New Roman",
                                    "Georgia",
                                    "Calibri",
                                    "Verdana",
                                    "Trebuchet MS",
                                ]
                                
                                for layer in layers:
                                    lid = layer.get("id")
                                    box = layer.get("box")
                                    if not lid or not box:
                                        continue
                                    
                                    st.markdown(f"#### **Placeholder: {lid}**")
                                    
                                    # Layout controls
                                    current_layout = st.session_state.bulk_layout_overrides.get(lid, box)
                                    c1, c2 = st.columns(2)
                                    c1.slider(f"X position ({lid})", 0, canvas_w, int(current_layout.get("x", box["x"])), key=f"bsx_{lid}")
                                    c2.slider(f"Y position ({lid})", 0, canvas_h, int(current_layout.get("y", box["y"])), key=f"bsy_{lid}")
                                    
                                    # If it's a text layer, render font styling overrides
                                    ltype = str(layer.get("type", "")).lower()
                                    if ltype == "text":
                                        current_style = st.session_state.bulk_style_overrides.get(lid, {})
                                        style = layer.get("style", {})

                                        # 1. Font Family & Weight
                                        cs1, cs2 = st.columns(2)
                                        
                                        current_font = current_style.get("font_family", "(Template default)")
                                        font_idx = 0
                                        if current_font in FONT_OPTIONS:
                                            font_idx = FONT_OPTIONS.index(current_font)
                                            
                                        cs1.selectbox(
                                            f"Font family ({lid})",
                                            options=FONT_OPTIONS,
                                            index=font_idx,
                                            key=f"bfont_{lid}"
                                        )
                                        
                                        current_weight = current_style.get("font_weight", "regular")
                                        weight_val = "(Template default)"
                                        if current_weight == "bold":
                                            weight_val = "Bold"
                                        elif current_weight == "regular":
                                            weight_val = "Normal"
                                            
                                        cs2.radio(
                                            f"Font weight ({lid})",
                                            options=["(Template default)", "Bold", "Normal"],
                                            index=["(Template default)", "Bold", "Normal"].index(weight_val),
                                            horizontal=True,
                                            key=f"bweight_{lid}"
                                        )

                                        # 2. Font Size & Text Color
                                        cs3, cs4 = st.columns(2)
                                        
                                        size_overridden = "font_size" in current_style
                                        use_size = cs3.checkbox(f"Override font size ({lid})", value=size_overridden, key=f"buse_size_{lid}")
                                        cs3.slider(
                                            f"Font size (px) ({lid})",
                                            min_value=12,
                                            max_value=96,
                                            value=int(current_style.get("font_size", style.get("font_size", 48))),
                                            step=2,
                                            disabled=not use_size,
                                            key=f"bsize_{lid}"
                                        )

                                        color_overridden = "color" in current_style
                                        use_color = cs4.checkbox(f"Override text colour ({lid})", value=color_overridden, key=f"buse_color_{lid}")
                                        cs4.color_picker(
                                            f"Text colour ({lid})",
                                            value=current_style.get("color", style.get("color", "#FFFFFF")),
                                            disabled=not use_color,
                                            key=f"bcolor_{lid}"
                                        )
                                    
                                    st.markdown("---")

                        st.success(
                            f"Matched template: **{body['template_id']}** (folder: `{body['folder']}`)."
                        )
                        st.markdown(
                            f"**Do you wish to proceed and generate all {body['total_rows']} posters?**"
                        )

                        col_yes, col_no = st.columns([1, 1])
                        with col_yes:
                            if st.button("Yes, proceed with all", type="primary", use_container_width=True):
                                with st.spinner("Starting bulk generation job…"):
                                    # Post to /bulk to start the background job
                                    try:
                                        res_job = requests.post(
                                            f"{API}/bulk",
                                            data=data,
                                            files=files,
                                            timeout=30,
                                        )
                                        job_body = res_job.json()
                                        if res_job.status_code == 200 and "job_id" in job_body:
                                            st.session_state.bulk_job_id = job_body["job_id"]
                                            st.session_state.bulk_total = job_body.get("total_rows", 0)
                                            st.session_state.bulk_done = False
                                            st.session_state.bulk_error = None
                                            st.session_state.bulk_download_url = None
                                            st.session_state.bulk_started = False
                                            st.rerun()
                                        else:
                                            st.error(f"Failed to start bulk job: {job_body}")
                                    except Exception as exc:
                                        st.error(f"Error starting bulk job: {exc}")

                        with col_no:
                            if st.button("Cancel & start over", type="secondary", use_container_width=True):
                                _reset_bulk()
                                st.rerun()

                    elif res.status_code == 422:
                        st.error("Excel validation failed:")
                        for err in body.get("errors", []):
                            st.warning(f"• {err}")

                        layers = body.get("overlay_layers") or []
                        if layers:
                            st.info("Map the mismatching columns below to resolve the errors:")
                            # Column Mapper Expander
                            with st.expander("Review & Adjust Column Mapping", expanded=True):
                                st.caption("Choose which Excel column maps to each template placeholder.")
                                backend_col_map = body.get("column_map") or {}
                                for layer in layers:
                                    lid = layer.get("id")
                                    ltype = str(layer.get("type", "")).lower()
                                    can_invent = bool(layer.get("llm_can_invent", False))
                                    if not lid or ltype == "image" or can_invent:
                                        continue
                                    
                                    current_mapped_col = st.session_state.bulk_column_mapping.get(lid)
                                    if not current_mapped_col:
                                        current_mapped_col = backend_col_map.get(lid, "")
                                    
                                    options = ["(Choose column...)"] + excel_columns
                                    default_idx = 0
                                    if current_mapped_col in excel_columns:
                                        default_idx = options.index(current_mapped_col)
                                    
                                    st.selectbox(
                                        f"Field: **{lid}**",
                                        options=options,
                                        index=default_idx,
                                        key=f"bmap_{lid}"
                                    )

                        if st.button("Cancel & start over", type="secondary"):
                            _reset_bulk()
                            st.rerun()

                    elif body.get("suggest_create"):
                        st.error("No matching template found for that prompt.")
                        st.info("Try a different description, or create a new template.")
                        if st.button("Cancel & start over", type="secondary"):
                            _reset_bulk()
                            st.rerun()

                    else:
                        st.error(f"Unexpected response ({res.status_code}): {body}")
                        if st.button("Cancel & start over", type="secondary"):
                            _reset_bulk()
                            st.rerun()

                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to backend. Make sure uvicorn is running.")
                except Exception as exc:
                    import streamlit.runtime.scriptrunner as _sr
                    if isinstance(exc, _sr.StopException) or "RerunData" in type(exc).__name__ or "RerunException" in type(exc).__name__:
                        raise
                    st.error(f"Error: {exc}")
        else:
            col_submit, col_hint = st.columns([1, 2])
            with col_submit:
                if st.button("Generate Preview", type="primary", key="btn_bulk_preview"):
                    if not bulk_prompt.strip():
                        st.error("Please describe the poster type.")
                    elif bulk_excel is None:
                        st.error("Please upload an Excel file.")
                    else:
                        st.session_state.bulk_started = True
                        st.rerun()
            with col_hint:
                st.caption("You will see a preview of the first poster before starting bulk run.")

    # ── Step 2: Progress polling (shown while job is running) ──────────────
    else:
        job_id = st.session_state.bulk_job_id

        # Poll the backend for current status
        try:
            poll = requests.get(f"{API}/job-status/{job_id}", timeout=10)
            job = poll.json()
        except Exception as exc:
            st.error(f"Could not reach backend: {exc}")
            if st.button("Reset"):
                _reset_bulk()
                st.rerun()
            st.stop()

        status      = job.get("status", "processing")
        completed   = int(job.get("completed", 0))
        total       = int(job.get("total", st.session_state.bulk_total)) or 1
        error_msg   = job.get("error", "")
        download_url = job.get("download_url", "")

        # ── Done ───────────────────────────────────────────────────────────
        if status == "done":
            st.success(f"Done! **{completed}** poster(s) generated successfully.")

            # Show progress bar at 100 %
            st.progress(1.0)

            # Download button — fetch ZIP from backend and hand to browser
            if download_url:
                full_url = f"{API}{download_url}"
                try:
                    zip_resp = requests.get(full_url, timeout=60)
                    if zip_resp.status_code == 200:
                        st.download_button(
                            label="⬇Download ZIP (all posters)",
                            data=zip_resp.content,
                            file_name=f"posters_{job_id[:8]}.zip",
                            mime="application/zip",
                            type="primary",
                        )
                    else:
                        st.error("ZIP file not ready yet — try again in a moment.")
                except Exception as exc:
                    st.error(f"Could not fetch ZIP: {exc}")

            # Audit note
            st.caption(
                "If any rows were skipped (missing fields / render errors), "
                "an **audit_skipped.csv** file is included inside the ZIP."
            )

            if st.button("Start another batch"):
                _reset_bulk()
                st.rerun()

        # ── Failed ─────────────────────────────────────────────────────────
        elif status == "failed":
            st.error(f"Job failed: {error_msg or 'Unknown error'}")
            if st.button("Try again"):
                _reset_bulk()
                st.rerun()

        # ── Still processing ───────────────────────────────────────────────
        else:
            pct = completed / total if total else 0

            st.markdown(f"**Job ID:** `{job_id[:16]}…`")
            st.markdown(
                f'<p class="progress-label">Processing… {completed} / {total} posters</p>',
                unsafe_allow_html=True,
            )
            st.progress(pct)

            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.metric("Completed", completed)
            with col_b:
                st.metric("Remaining", total - completed)

            st.caption("This page auto-refreshes every 2 seconds.")

            # Auto-refresh while processing
            time.sleep(2)
            st.rerun()