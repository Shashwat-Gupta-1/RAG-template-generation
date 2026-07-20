"""
create_template_page.py
========================

Streamlit UI for the MS Fincap AI Template Creator.

All LLM / graph / session logic lives in `backend/phase2/create_agent.py`. This file is
purely presentational: it renders the 5-step wizard (chat -> upload PNG ->
draw zones -> preview -> save) and drives `SessionAgent`.
"""

import io
import os
import sys

import streamlit as st
from PIL import Image
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from validation.logging_config import setup_logging, get_logger  # noqa: E402
from auth_utils import auth_gate, get_auth_headers
from history_utils import render_history_sidebar

st.set_page_config(page_title="Create Template", layout="wide")

# Run Auth Gate
if not auth_gate():
    st.stop()

# Render History Sidebar
render_history_sidebar()

API = "http://127.0.0.1:8000"

setup_logging()
logger = get_logger("CreateTemplatePage")

# pyrefly: ignore [missing-import]
from streamlit_drawable_canvas import st_canvas  # noqa: E402



# ---------------------------------------------------------------------------
# Small filesystem helpers used only by the Save step (UI concerns, not agent logic)
# ---------------------------------------------------------------------------
def get_existing_categories():
    """Scans templates/ directory for subdirectories."""
    templates_dir = "templates"
    if not os.path.exists(templates_dir):
        return []
    try:
        return sorted(
            name for name in os.listdir(templates_dir)
            if os.path.isdir(os.path.join(templates_dir, name))
        )
    except Exception:
        return []


def validate_subfolder_name(subfolder_name: str, category_name: str):
    """Validates that the subfolder name does not conflict with existing category folder names."""
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


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.title("Create a new template with AI")

# Register state fields
for key, default in [
    ("ca_messages", []),
    ("ca_png_bytes", None),
    ("ca_img_w", 0),
    ("ca_img_h", 0),
    ("ca_field_configs", {}),
    ("ca_overlay", None),
    ("ca_step", "chat"),
    ("ca_thread_id", None),
    ("ca_assumptions", {}),
    ("ca_ready", False),
    ("ca_generated_image_path", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# Initialize ca_thread_id dynamically
if not st.session_state.ca_thread_id:
    headers = get_auth_headers()
    try:
        resp = requests.post(f"{API}/agent/conversations", headers=headers)
        if resp.status_code == 200:
            st.session_state.ca_thread_id = resp.json()["conversation_id"]
            st.session_state.ca_messages = []
        else:
            st.error("Failed to start a template creation session.")
            st.stop()
    except Exception as e:
        st.error(f"Could not connect to backend: {e}")
        st.stop()

# Initialize assumption + prompt widget keys in session state
ASS_FIELDS = [
    "occasion", "purpose", "audience", "colour_palette", "style",
    "layout_composition", "text_placeholders", "photo_placeholders",
    "logo_position", "mascot_position",
]
for f in ASS_FIELDS:
    skey = f"ca_ass_val_{f}"
    if skey not in st.session_state:
        st.session_state[skey] = ""

if "ca_prompt_textarea" not in st.session_state:
    st.session_state["ca_prompt_textarea"] = ""


def _sync_assumption_widgets_from_state():
    """Pushes assumptions into the ca_ass_val_* widget keys (used right
    after the graph updates assumptions, e.g. after a chat turn)."""
    assumptions = st.session_state.get("ca_assumptions") or {}
    for k in ASS_FIELDS:
        v = assumptions.get(k, "")
        st.session_state[f"ca_ass_val_{k}"] = v or ""


def _reset_assumption_widgets():
    for k in ASS_FIELDS:
        st.session_state[f"ca_ass_val_{k}"] = ""
    st.session_state["ca_prompt_textarea"] = ""



STEPS = ["chat", "upload", "zone_map", "preview", "save"]
step_labels = {
    "chat": "1. Describe",
    "upload": "2. Upload PNG",
    "zone_map": "3. Draw boxes",
    "preview": "4. Preview",
    "save": "5. Save",
}
current_step = st.session_state.ca_step
st.write(
    " → ".join(
        f"**{v}**" if k == current_step else v
        for k, v in step_labels.items()
    )
)
st.divider()

# ── STEP 1: Agent chat ─────────────────────────────────────────────────
if st.session_state.ca_step == "chat":
    # Greeting trigger if chat history is empty
    if not st.session_state.ca_messages:
        headers = get_auth_headers()
        try:
            resp = requests.post(
                f"{API}/agent/chat",
                json={"conversation_id": st.session_state.ca_thread_id},
                headers=headers
            )
            if resp.status_code == 200:
                body = resp.json()
                st.session_state.ca_messages = [{"role": "assistant", "content": body["reply"]}]
                st.session_state.ca_assumptions = body["assumptions"]
                st.session_state.ca_ready = body["ready"]
                _sync_assumption_widgets_from_state()
                if body.get("ready") and "generated_prompt" in body and body["generated_prompt"]:
                    st.session_state["ca_prompt_textarea"] = body["generated_prompt"]
            else:
                st.error("Failed to load greeting.")
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")

    col_chat, col_details = st.columns([1, 1])

    with col_chat:
        st.subheader("Creative Director Chat")

        for msg in st.session_state.ca_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        openrouter_key_present = bool(os.getenv("OPENROUTER_API_KEY", "").strip())
        if not openrouter_key_present:
            st.error(
                "OPENROUTER_API_KEY is not set (checked environment and .env). "
                "The agent cannot reply until this is fixed. Make sure a `.env` "
                "file exists in the project root."
            )

        if user_input := st.chat_input("Message the Creative Director..."):
            try:
                with st.spinner("Creative Director is thinking..."):
                    headers = get_auth_headers()
                    resp = requests.post(
                        f"{API}/agent/chat",
                        json={"conversation_id": st.session_state.ca_thread_id, "message": user_input},
                        headers=headers
                    )
                    if resp.status_code == 200:
                        body = resp.json()
                        st.session_state.ca_messages = st.session_state.ca_messages + [
                            {"role": "user", "content": user_input},
                            {"role": "assistant", "content": body["reply"]}
                        ]
                        st.session_state.ca_assumptions = body["assumptions"]
                        st.session_state.ca_ready = body["ready"]
                        _sync_assumption_widgets_from_state()
                        if body.get("ready") and "generated_prompt" in body and body["generated_prompt"]:
                            st.session_state["ca_prompt_textarea"] = body["generated_prompt"]
                    else:
                        st.error("Failed to get agent reply.")
                st.rerun()
            except Exception as e:
                if type(e).__name__ in ("RerunException", "StopException"):
                    raise e
                st.exception(e)

    with col_details:
        st.subheader("Design Details & Customization")

        # Render Assumptions Form
        assumptions = st.session_state.get("ca_assumptions") or {}
        if assumptions:
            with st.expander("Editable Design Assumptions", expanded=True):
                with st.form("assumptions_form"):
                    st.caption("Review or edit the design assumptions inferred by the Creative Director:")

                    for key in assumptions.keys():
                        label = key.replace("_", " ").title()
                        st.text_input(label, key=f"ca_ass_val_{key}")

                    user_edits = st.text_area("Additional visual constraints / styling instructions", value="")

                    submitted = st.form_submit_button("Rebuild Prompt from Assumptions 🛠️")
                    if submitted:
                        try:
                            edited_assumptions = {
                                k: st.session_state.get(f"ca_ass_val_{k}", "")
                                for k in assumptions.keys()
                            }
                            with st.spinner("Building new prompt..."):
                                headers = get_auth_headers()
                                resp = requests.post(
                                    f"{API}/agent/rebuild-prompt",
                                    json={
                                        "conversation_id": st.session_state.ca_thread_id,
                                        "assumptions": edited_assumptions,
                                        "user_edits": user_edits
                                    },
                                    headers=headers
                                )
                                if resp.status_code == 200:
                                    body = resp.json()
                                    st.session_state.ca_assumptions = edited_assumptions
                                    st.session_state["ca_prompt_textarea"] = body["generated_prompt"]
                                    st.success("Prompt rebuilt!")
                                else:
                                    st.error("Failed to rebuild prompt.")
                            st.rerun()
                        except Exception as e:
                            if type(e).__name__ in ("RerunException", "StopException"):
                                raise e
                            st.exception(e)

        # Render Prompt Editor & History if a prompt has been generated
        if st.session_state.get("ca_ready") or st.session_state.get("ca_prompt_textarea"):
            st.subheader("Image Generation Prompt")

            st.text_area(
                "Edit Prompt directly if needed",
                key="ca_prompt_textarea",
                height=150,
            )

            with st.form("refine_form"):
                refine_input = st.text_input(
                    "Refinement Instructions",
                    placeholder="e.g., make it a darker blue background, make it look more premium",
                )
                refine_submitted = st.form_submit_button("Refine Prompt with AI 🪄")
                if refine_submitted and refine_input.strip():
                    try:
                        with st.spinner("Refining prompt..."):
                            headers = get_auth_headers()
                            resp = requests.post(
                                f"{API}/agent/refine-prompt",
                                json={
                                    "conversation_id": st.session_state.ca_thread_id,
                                    "refinement_request": refine_input
                                },
                                headers=headers
                            )
                            if resp.status_code == 200:
                                body = resp.json()
                                st.session_state["ca_prompt_textarea"] = body["generated_prompt"]
                                st.success("Prompt refined!")
                            else:
                                st.error("Failed to refine prompt.")
                        st.rerun()
                    except Exception as e:
                        if type(e).__name__ in ("RerunException", "StopException"):
                            raise e
                        st.exception(e)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Generate Template Image with AI 🚀", type="primary"):
                    with st.spinner("Generating template image with AI... (this may take up to 40s)"):
                        try:
                            # Re-verify/save custom prompt if they edited the text area directly first
                            headers = get_auth_headers()
                            resp_gen = requests.post(
                                f"{API}/agent/generate-image",
                                json={"conversation_id": st.session_state.ca_thread_id},
                                headers=headers
                            )
                            if resp_gen.status_code == 200:
                                body = resp_gen.json()
                                st.session_state.ca_generated_image_path = body["image_path"]
                                st.session_state.ca_step = "upload"
                            else:
                                st.error(f"Image generation failed: {resp_gen.text}")
                                st.stop()
                        except Exception as e:
                            st.exception(e)
                            st.stop()
                    st.rerun()
            with col2:
                if st.button("Skip AI image — upload PNG directly →"):
                    st.session_state.ca_step = "upload"
                    st.rerun()
        else:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Skip chat — upload PNG directly →"):
                    st.session_state.ca_step = "upload"
                    st.rerun()
            with col2:
                if st.button("Reset conversation"):
                    # Create new thread/conversation session
                    headers = get_auth_headers()
                    try:
                        resp = requests.post(f"{API}/agent/conversations", headers=headers)
                        if resp.status_code == 200:
                            st.session_state.ca_thread_id = resp.json()["conversation_id"]
                            st.session_state.ca_messages = []
                            st.session_state.ca_assumptions = {}
                            st.session_state.ca_ready = False
                            st.session_state.ca_generated_image_path = None
                            _reset_assumption_widgets()
                        else:
                            st.error("Failed to reset session.")
                    except Exception as e:
                        st.error(f"Error resetting session: {e}")
                    st.rerun()

# ── STEP 2: Upload PNG ─────────────────────────────────────────────────
elif st.session_state.ca_step == "upload":
    st.subheader("Template Image Source")

    image_path = st.session_state.get("ca_generated_image_path")
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            gen_bytes = f.read()
        img = Image.open(io.BytesIO(gen_bytes))

        if st.session_state.ca_png_bytes is None:
            st.session_state.ca_png_bytes = gen_bytes
            st.session_state.ca_img_w, st.session_state.ca_img_h = img.size

        st.image(gen_bytes, caption=f"AI Generated Image ({img.size[0]} × {img.size[1]} px)")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Continue with this AI image →", type="primary"):
                st.session_state.ca_png_bytes = gen_bytes
                st.session_state.ca_img_w, st.session_state.ca_img_h = img.size
                st.session_state.ca_step = "zone_map"
                st.rerun()
        with c2:
            if st.button("Regenerate image ↺"):
                with st.spinner("Generating new image..."):
                    try:
                        headers = get_auth_headers()
                        resp_gen = requests.post(
                            f"{API}/agent/generate-image",
                            json={"conversation_id": st.session_state.ca_thread_id},
                            headers=headers
                        )
                        if resp_gen.status_code == 200:
                            body = resp_gen.json()
                            st.session_state.ca_generated_image_path = body["image_path"]
                            st.session_state.ca_png_bytes = None
                            st.success("New image generated!")
                        else:
                            st.error("Failed to generate image.")
                        st.rerun()
                    except Exception as e:
                        if type(e).__name__ in ("RerunException", "StopException"):
                            raise e
                        st.error(f"Failed to generate new image: {e}")

        st.write("---")
        st.write("#### Or upload a different PNG file instead:")

    uploaded = st.file_uploader("Select your poster PNG file", type=["png", "jpg", "jpeg"])
    if uploaded:
        png_bytes = uploaded.read()
        img = Image.open(io.BytesIO(png_bytes))
        st.session_state.ca_png_bytes = png_bytes
        st.session_state.ca_img_w, st.session_state.ca_img_h = img.size
        st.image(png_bytes, caption=f"{img.size[0]} × {img.size[1]} px")
        if st.button("Continue — draw placeholder boxes →", type="primary"):
            st.session_state.ca_step = "zone_map"
            st.rerun()

    if st.button("← Back to chat"):
        st.session_state.ca_step = "chat"
        st.rerun()

# ── STEP 3: Zone mapper ────────────────────────────────────────────────
elif st.session_state.ca_step == "zone_map":
    st.subheader("Draw placeholder boxes on your template")
    st.caption(
        "Drag to draw a rectangle wherever you want text or an image. "
        "Configure each field below the canvas."
    )

    img_w = st.session_state.ca_img_w
    img_h = st.session_state.ca_img_h
    DISPLAY_W = 680
    scale = DISPLAY_W / img_w
    display_h = int(img_h * scale)

    img = Image.open(io.BytesIO(st.session_state.ca_png_bytes))

    canvas_result = st_canvas(
        background_image=img,
        drawing_mode="rect",
        stroke_width=2,
        stroke_color="#4F8EF7",
        fill_color="rgba(79,142,247,0.15)",
        height=display_h,
        width=DISPLAY_W,
        key="ca_canvas",
    )

    objects = []
    if canvas_result.json_data:
        objects = canvas_result.json_data.get("objects", [])

    if not objects:
        st.info("Draw at least one box on the image above.")
    else:
        st.write(f"**{len(objects)} box(es) placed.** Configure below:")
        field_configs = {}

        for i, obj in enumerate(objects):
            with st.expander(f"Field {i + 1}", expanded=(i == 0)):
                c1, c2 = st.columns(2)
                with c1:
                    fid = st.text_input(
                        "Field ID (must match Excel column name)",
                        value=f"field_{i + 1}",
                        key=f"ca_fid_{i}",
                    )
                    ftype = st.selectbox("Field type", ["text", "image"], key=f"ca_ftype_{i}")
                    instruction = st.text_input(
                        "Instruction for AI", value=f"Enter value for {fid}", key=f"ca_finstr_{i}"
                    )
                    llm_invent = st.checkbox(
                        "AI can generate this if not provided", value=False, key=f"ca_llmi_{i}"
                    )
                with c2:
                    if ftype == "text":
                        ff = st.selectbox(
                            "Font", ["Poppins", "NotoSans", "NotoSansDevanagari"], key=f"ca_ff_{i}"
                        )
                        fs = st.number_input("Font size", 8, 200, 48, key=f"ca_fs_{i}")
                        fsmin = st.number_input("Min font size", 6, 100, 20, key=f"ca_fsmin_{i}")
                        fw = st.selectbox("Weight", ["bold", "normal", "semibold"], key=f"ca_fw_{i}")
                        fc = st.color_picker("Text colour", "#FFFFFF", key=f"ca_fc_{i}")
                        fa = st.selectbox("Align", ["center", "left", "right"], key=f"ca_fa_{i}")
                        field_configs[str(i)] = {
                            "id": fid, "type": ftype, "instruction": instruction,
                            "llm_can_invent": llm_invent, "font_family": ff, "font_size": fs,
                            "font_size_min": fsmin, "font_weight": fw, "color": fc, "align": fa,
                        }
                    else:
                        shape = st.selectbox("Shape", ["circle", "rectangle"], key=f"ca_fsh_{i}")
                        bc = st.color_picker("Border colour", "#FFFFFF", key=f"ca_fbc_{i}")
                        bw = st.number_input("Border width px", 0, 20, 4, key=f"ca_fbw_{i}")
                        field_configs[str(i)] = {
                            "id": fid, "type": ftype, "instruction": instruction,
                            "llm_can_invent": False, "shape": shape,
                            "border_color": bc, "border_width": bw,
                        }

        st.session_state.ca_field_configs = field_configs

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Back to upload"):
                st.session_state.ca_step = "upload"
                st.rerun()
        with c2:
            if st.button("Build overlay and preview →", type="primary"):
                from phase2.zone_mapper import canvas_objects_to_overlay_layers, validate_layers

                layers = canvas_objects_to_overlay_layers(
                    objects, field_configs, img_w, img_h, DISPLAY_W, display_h
                )
                errors = validate_layers(layers, img_w, img_h)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    st.session_state.ca_overlay = {
                        "overlay_layers": layers,
                        "canvas": {"width": img_w, "height": img_h},
                    }
                    st.session_state.ca_step = "preview"
                    st.rerun()

# ── STEP 4: Preview ────────────────────────────────────────────────────
elif st.session_state.ca_step == "preview":
    st.subheader("Preview your template")
    overlay = st.session_state.ca_overlay

    with st.expander("overlay.json (click to inspect)", expanded=False):
        st.json(overlay)

    sample_values = {
        layer["id"]: f"[{layer['id']}]"
        for layer in overlay.get("overlay_layers", [])
        if layer["type"] == "text"
    }

    if st.button("Render preview with sample values", type="primary"):
        import uuid as _uuid

        os.makedirs("output", exist_ok=True)
        tmp = f"output/ca_tmp_{_uuid.uuid4().hex}.png"
        with open(tmp, "wb") as f:
            f.write(st.session_state.ca_png_bytes)

        test_overlay = {
            **overlay,
            "template_id": "_preview",
            "base_image": tmp,
            "description": "preview",
            "tags": [],
            "type": "poster",
        }

        try:
            from processing.renderer import render_poster

            out = f"output/ca_preview_{_uuid.uuid4().hex}.png"
            render_poster(test_overlay, sample_values, out)
            st.image(out, caption="Sample preview — field names shown as labels")
            os.remove(tmp)
        except Exception as e:
            st.error(f"Preview render failed: {e}")
            if os.path.exists(tmp):
                os.remove(tmp)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Revise boxes"):
            st.session_state.ca_step = "zone_map"
            st.rerun()
    with c2:
        if st.button("Looks good — save →", type="primary"):
            st.session_state.ca_step = "save"
            st.rerun()

# ── STEP 5: Save ──────────────────────────────────────────────────────
elif st.session_state.ca_step == "save":
    st.subheader("Save your template")
    overlay = st.session_state.ca_overlay
    field_ids = [l["id"] for l in overlay.get("overlay_layers", []) if l["type"] == "text"]
    instructions = [l["instruction"] for l in overlay.get("overlay_layers", []) if l["type"] == "text"]

    existing_categories = get_existing_categories()
    cat_options = existing_categories + ["Create new folder..."]
    selected_cat = st.selectbox(
        "Category folder name",
        options=cat_options,
        help="Select an existing templates category folder or create a new one",
    )

    if selected_cat == "Create new folder...":
        category = st.text_input(
            "Enter new category folder name",
            placeholder="diwali",
            help="Lowercase, no spaces. e.g. holi, diwali, hiring",
        ).strip().lower()
    else:
        category = selected_cat.strip()

    base_id = st.text_input(
        "Subfolder/Template base ID",
        placeholder="diwali",
        help=(
            "Cannot match the category folder name or any other templates category folder name. "
            "If name already exists in target category, system saves with sequential number automatically."
        ),
    )
    hint = st.text_area(
        "Brief description (AI will enrich this for better search)",
        placeholder="Diwali festival greeting poster for MS Fincap employees",
        height=80,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Back to preview"):
            st.session_state.ca_step = "preview"
            st.rerun()
    with c2:
        if st.button("Generate tags and save", type="primary"):
            validation_error = validate_subfolder_name(base_id, category)
            if not category or not base_id.strip():
                st.error("Both category and subfolder/template ID are required.")
            elif validation_error:
                st.error(validation_error)
            else:
                with st.spinner("Generating smart tags and saving template..."):
                    from processing.llm import generate_tags_and_description

                    try:
                        meta = generate_tags_and_description(
                            category.strip(), field_ids, instructions, hint.strip()
                        )
                    except Exception as e:
                        st.error(f"Tag generation failed: {e}")
                        st.stop()

                    full_overlay = {
                        "template_id": base_id.strip(),
                        "description": meta["description"],
                        "type": "poster",
                        "tags": meta["tags"],
                        "base_image": "",
                        "canvas": overlay["canvas"],
                        "overlay_layers": overlay["overlay_layers"],
                    }

                    from phase2.template_saver import save_template_files

                    try:
                        _, resolved_id = save_template_files(
                            st.session_state.ca_png_bytes, full_overlay, category.strip(), base_id.strip()
                        )
                        st.success(
                            f"Saved as `{resolved_id}` in `{category.strip()}/` — searchable immediately!"
                        )
                        st.balloons()
                        st.session_state.ca_thread_id = None
                        st.session_state.ca_assumptions = {}
                        st.session_state.ca_ready = False
                        st.session_state.ca_generated_image_path = None
                        _reset_assumption_widgets()
                        for k in ["ca_messages", "ca_png_bytes", "ca_img_w", "ca_img_h", "ca_field_configs", "ca_overlay"]:
                            default_vals = {
                                "ca_messages": [],
                                "ca_png_bytes": None,
                                "ca_img_w": 0,
                                "ca_img_h": 0,
                                "ca_field_configs": {},
                                "ca_overlay": None,
                            }
                            st.session_state[k] = default_vals[k]
                        st.session_state.ca_step = "chat"
                    except Exception as e:
                        st.error(f"Save failed: {e}")