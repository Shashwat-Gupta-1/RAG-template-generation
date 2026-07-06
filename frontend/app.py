import time
import json
import base64
# pyrefly: ignore [missing-import]
import streamlit as st
import requests

API = "http://localhost:8000"

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
    "bulk_style_overrides": None,
    "single_started": False,
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
        st.session_state.extra_fields = {}
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

    # ── Styling Options ───────────────────────────────────────────────────
    with st.expander("Styling Options (optional)", expanded=False):
        st.caption(
            "Override the template's default text style. "
            "Leave unchanged to use the template's built-in styling."
        )
        style_col1, style_col2 = st.columns(2)

        with style_col1:
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
            style_font = st.selectbox(
                "Font family",
                options=FONT_OPTIONS,
                index=0,
                key="style_font",
            )
            style_weight = st.radio(
                "Font weight",
                options=["(Template default)", "Bold", "Normal"],
                horizontal=True,
                key="style_weight",
            )

        with style_col2:
            style_use_size = st.checkbox("Override font size", key="style_use_size")
            style_size = st.slider(
                "Font size (px)",
                min_value=12,
                max_value=96,
                value=48,
                step=2,
                key="style_size",
                disabled=not style_use_size,
            )
            style_use_color = st.checkbox("Override text colour", key="style_use_color")
            style_color = st.color_picker(
                "Text colour",
                value="#FFFFFF",
                key="style_color",
                disabled=not style_use_color,
            )

    # Build style overrides dictionary
    _overrides: dict = {}
    if style_font != "(Template default)":
        _overrides["font_family"] = style_font
    if style_weight == "Bold":
        _overrides["font_weight"] = "bold"
    elif style_weight == "Normal":
        _overrides["font_weight"] = "regular"
    if style_use_size:
        _overrides["font_size"] = style_size
    if style_use_color:
        _overrides["color"] = style_color

    # 2. Design Selection and Live Preview section (Vertical Flow)
    if st.session_state.single_started:
        if prompt.strip():
            # Gather base values to hit endpoint and fetch preview or needs_input
            data = {
                "prompt": prompt.strip(),
                "folder": st.session_state.selected_folder or "",
                "template_id": st.session_state.selected_template_id or "",
            }
            if _overrides:
                data["style_overrides"] = json.dumps(_overrides)

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
                        f"{API}/generate",
                        data=data,
                        files=files or None,
                        timeout=30,
                    )
                
            except Exception as exc:
                st.error(f"Could not connect to backend: {exc}")
                res = None
            
            if res is not None:
                if res.headers.get("content-type", "").startswith("image"):
                    # Poster is generated successfully! Show it vertically
                    st.subheader("Live Preview")
                    st.image(res.content, caption="Live Preview (updates as you change inputs)", use_column_width=True)
                    
                    col_dl, col_reset = st.columns([3, 1])
                    with col_dl:
                        st.download_button(
                            label="Download Poster",
                            data=res.content,
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
                    resp = res.json()
                    status = resp.get("status")

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
                        st.info(f"Found {resp['display_name']} designs:")
                        for t in resp["templates"]:
                            col_t1, col_t2 = st.columns([3, 1])
                            with col_t1:
                                st.write(f"**{t['template_id']}** — {t['description']}")
                            with col_t2:
                                if st.button("Use this", key=f"tmpl_{t['template_id']}"):
                                    st.session_state.selected_folder = resp["folder"]
                                    st.session_state.selected_template_id = t["template_id"]
                                    st.rerun()

                    elif status == "needs_input":
                        # Display the missing fields to be filled
                        st.write("**Please fill in the poster details:**")
                        for fid in resp["missing_fields"]:
                            st.text_input(
                                fid.replace("_", " ").title(),
                                placeholder=f"Enter {fid}",
                                key=f"field_{fid}",
                            )
                        # Automatically lock the resolved design in session state
                        st.session_state.selected_folder = resp.get("folder")
                        st.session_state.selected_template_id = resp.get("template_id")
                        st.info("Fill in the fields above to see the live preview here.")
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
        st.session_state.bulk_style_overrides = None

    # ── Step 1: Input / Preview stage (shown when no job is running) ───────
    if not st.session_state.bulk_job_id:
        
        # Scenario A: User needs to confirm the preview
        if st.session_state.bulk_preview:
            st.info("Preview generated for the first row of your Excel sheet")
            
            try:
                img_data = base64.b64decode(st.session_state.bulk_preview["preview_image"])
                st.image(img_data, caption="First poster preview", use_column_width=True)
            except Exception as e:
                st.error(f"Failed to show preview image: {e}")
                
            st.success(
                f"Matched template: **{st.session_state.bulk_preview['template_id']}** "
                f"(folder: `{st.session_state.bulk_preview['folder']}`)."
            )
            st.markdown(
                f"**Do you wish to proceed and generate the remaining "
                f"{st.session_state.bulk_preview['total_rows']} posters?**"
            )
            
            col_yes, col_no = st.columns([1, 1])
            with col_yes:
                if st.button("Yes, proceed with all", type="primary", use_container_width=True):
                    with st.spinner("Starting bulk generation job…"):
                        # Retrieve files from state
                        f_name, f_bytes = st.session_state.bulk_file_data
                        files = {
                            "excel_file": (
                                f_name,
                                f_bytes,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            ),
                        }
                        if st.session_state.bulk_photo_data:
                            ph_name, ph_bytes, ph_type = st.session_state.bulk_photo_data
                            files["photo"] = (ph_name, ph_bytes, ph_type)

                        data = {"prompt": st.session_state.bulk_prompt_data}
                        if st.session_state.bulk_style_overrides:
                            data["style_overrides"] = json.dumps(st.session_state.bulk_style_overrides)

                        try:
                            res = requests.post(
                                f"{API}/bulk",
                                data=data,
                                files=files,
                                timeout=30,
                            )
                            body = res.json()
                            if res.status_code == 200 and "job_id" in body:
                                st.session_state.bulk_job_id = body["job_id"]
                                st.session_state.bulk_total = body.get("total_rows", 0)
                                st.session_state.bulk_done = False
                                st.session_state.bulk_error = None
                                st.session_state.bulk_download_url = None
                                # Clear preview state
                                st.session_state.bulk_preview = None
                                st.session_state.bulk_file_data = None
                                st.session_state.bulk_photo_data = None
                                st.session_state.bulk_prompt_data = None
                                st.session_state.bulk_style_overrides = None
                                st.rerun()
                            else:
                                st.error(f"Failed to start bulk job: {body}")
                        except Exception as exc:
                            st.error(f"Error starting bulk job: {exc}")

            with col_no:
                if st.button("Cancel & edit", type="secondary", use_container_width=True):
                    st.session_state.bulk_preview = None
                    st.session_state.bulk_file_data = None
                    st.session_state.bulk_photo_data = None
                    st.session_state.bulk_prompt_data = None
                    st.session_state.bulk_style_overrides = None
                    st.rerun()

        # Scenario B: Show input form
        else:
            bulk_prompt = st.text_area(
                "Describe the poster type",
                placeholder="e.g. Holi poster, Eid greetings, Hiring announcement…",
                height=80,
                help="This tells the system which template to use.",
            )

            bulk_excel = st.file_uploader(
                "Upload Excel file (.xlsx)",
                type=["xlsx", "xls"],
                help="Must contain an 'emp_id' column plus fields required by the template.",
            )

            bulk_photo = st.file_uploader(
                "Upload shared profile photo (optional)",
                type=["jpg", "jpeg", "png", "heic"],
                help="Used for templates with an image zone. Same photo applied to every poster.",
            )

            # ── Styling Options in Bulk ───────────────────────────────────
            with st.expander("Styling Options (optional)", expanded=False):
                st.caption(
                    "Override the template's default text style. "
                    "Leave unchanged to use the template's built-in styling."
                )
                style_col1, style_col2 = st.columns(2)

                with style_col1:
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
                    bulk_style_font = st.selectbox(
                        "Font family",
                        options=FONT_OPTIONS,
                        index=0,
                        key="bulk_style_font",
                    )
                    bulk_style_weight = st.radio(
                        "Font weight",
                        options=["(Template default)", "Bold", "Normal"],
                        horizontal=True,
                        key="bulk_style_weight",
                    )

                with style_col2:
                    bulk_style_use_size = st.checkbox("Override font size", key="bulk_style_use_size")
                    bulk_style_size = st.slider(
                        "Font size (px)",
                        min_value=12,
                        max_value=96,
                        value=48,
                        step=2,
                        key="bulk_style_size",
                        disabled=not bulk_style_use_size,
                    )
                    bulk_style_use_color = st.checkbox("Override text colour", key="bulk_style_use_color")
                    bulk_style_color = st.color_picker(
                        "Text colour",
                        value="#FFFFFF",
                        key="bulk_style_color",
                        disabled=not bulk_style_use_color,
                    )

            col_submit, col_hint = st.columns([1, 2])
            with col_submit:
                submitted = st.button("Generate Preview", type="primary", key="btn_bulk_preview")
            with col_hint:
                st.caption("You will see a preview of the first poster before starting bulk run.")

            # ── Handle form submission ─────────────────────────────────────────
            if submitted:
                if not bulk_prompt.strip():
                    st.error("Please describe the poster type.")
                elif bulk_excel is None:
                    st.error("Please upload an Excel file.")
                else:
                    with st.spinner("Generating preview…"):
                        # Build override dict — only include what the user explicitly enabled
                        _overrides: dict = {}
                        if bulk_style_font != "(Template default)":
                            _overrides["font_family"] = bulk_style_font
                        if bulk_style_weight == "Bold":
                            _overrides["font_weight"] = "bold"
                        elif bulk_style_weight == "Normal":
                            _overrides["font_weight"] = "regular"
                        if bulk_style_use_size:
                            _overrides["font_size"] = bulk_style_size
                        if bulk_style_use_color:
                            _overrides["color"] = bulk_style_color

                        excel_bytes = bulk_excel.getvalue()
                        files = {
                            "excel_file": (
                                bulk_excel.name,
                                excel_bytes,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            ),
                        }
                        photo_info = None
                        if bulk_photo:
                            photo_bytes = bulk_photo.getvalue()
                            files["photo"] = (bulk_photo.name, photo_bytes, bulk_photo.type)
                            photo_info = (bulk_photo.name, photo_bytes, bulk_photo.type)

                        data = {"prompt": bulk_prompt.strip()}
                        if _overrides:
                            data["style_overrides"] = json.dumps(_overrides)

                        try:
                            res = requests.post(
                                f"{API}/bulk/preview",
                                data=data,
                                files=files,
                                timeout=30,
                            )
                            body = res.json()

                            if res.status_code == 200 and "preview_image" in body:
                                # Save preview payload to session state
                                st.session_state.bulk_preview = body
                                # Keep raw file bytes so we can post them to /bulk on confirmation
                                st.session_state.bulk_file_data = (bulk_excel.name, excel_bytes)
                                st.session_state.bulk_photo_data = photo_info
                                st.session_state.bulk_prompt_data = bulk_prompt.strip()
                                st.session_state.bulk_style_overrides = _overrides if _overrides else None
                                st.rerun()

                            elif res.status_code == 422:
                                st.error("Excel validation failed:")
                                for err in body.get("errors", []):
                                    st.warning(f"• {err}")

                            elif body.get("suggest_create"):
                                st.error("No matching template found for that prompt.")
                                st.info("Try a different description, or create a new template.")

                            else:
                                st.error(f"Unexpected response ({res.status_code}): {body}")

                        except requests.exceptions.ConnectionError:
                            st.error("Cannot connect to backend. Make sure uvicorn is running.")
                        except Exception as exc:
                            import streamlit.runtime.scriptrunner as _sr
                            if isinstance(exc, _sr.StopException) or "RerunData" in type(exc).__name__ or "RerunException" in type(exc).__name__:
                                raise
                            st.error(f"Error: {exc}")

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