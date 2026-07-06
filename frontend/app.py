import time
import json
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
st.caption("Generate personalised posters — one at a time or in bulk from an Excel sheet.")

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
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
#  TAB LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
tab_single, tab_bulk = st.tabs(["📄 Single Poster", "📊 Bulk Generate (Excel)"])


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Single Poster (original flow, unchanged)
# ══════════════════════════════════════════════════════════════════════════════
with tab_single:
    st.subheader("Generate a single poster")

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

    # Build override dict — only include what the user explicitly enabled
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

    if st.button("Generate poster", type="primary", key="btn_single"):
        if not prompt.strip():
            st.warning("Please describe what you need.")
        else:
            with st.spinner("Finding the right template…"):
                data = {"prompt": prompt}
                if st.session_state.selected_folder:
                    data["folder"] = st.session_state.selected_folder
                if st.session_state.selected_template_id:
                    data["template_id"] = st.session_state.selected_template_id
                for k, v in st.session_state.extra_fields.items():
                    data[k] = v
                # Attach style overrides if any were set
                if _overrides:
                    data["style_overrides"] = json.dumps(_overrides)


                files = {}
                if photo:
                    files["image"] = (photo.name, photo.getvalue(), photo.type)

                try:
                    res = requests.post(
                        f"{API}/generate",
                        data=data,
                        files=files or None,
                        timeout=60,
                    )

                    if res.headers.get("content-type", "").startswith("image"):
                        st.success("Poster generated!")
                        st.image(res.content)
                        st.download_button(
                            "Download poster",
                            res.content,
                            "poster.png",
                            "image/png",
                        )
                        st.session_state.selected_folder = None
                        st.session_state.selected_template_id = None
                        st.session_state.extra_fields = {}
                    else:
                        resp = res.json()
                        status = resp.get("status")

                        if status == "no_match":
                            st.error("No matching template found.")
                            st.info("Would you like to create a new template?")
                            if st.button("Create new template"):
                                st.switch_page("pages/2_Add_Template.py")

                        elif status == "ambiguous":
                            st.warning("Which category did you mean?")
                            cols = st.columns(len(resp["matches"]))
                            for i, m in enumerate(resp["matches"]):
                                with cols[i]:
                                    if st.button(m["display_name"], key=f"cat_{m['folder']}"):
                                        st.session_state.selected_folder = m["folder"]
                                        st.rerun()

                        elif status == "gallery":
                            st.info(f"Found {resp['display_name']} templates. Which design?")
                            for t in resp["templates"]:
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.write(f"**{t['template_id']}** — {t['description']}")
                                with col2:
                                    if st.button("Use this", key=f"tmpl_{t['template_id']}"):
                                        st.session_state.selected_folder = resp["folder"]
                                        st.session_state.selected_template_id = t["template_id"]
                                        st.rerun()

                        elif status == "needs_input":
                            st.warning("We need a bit more information.")
                            with st.form("missing_fields"):
                                vals = {}
                                for fid in resp["missing_fields"]:
                                    vals[fid] = st.text_input(
                                        fid.replace("_", " ").title(),
                                        placeholder=f"Enter {fid}",
                                    )
                                if st.form_submit_button("Generate"):
                                    st.session_state.extra_fields = vals
                                    st.session_state.selected_folder = resp.get("folder")
                                    st.session_state.selected_template_id = resp.get("template_id")
                                    st.rerun()
                        else:
                            st.error(f"Unexpected response: {resp}")

                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to backend. Make sure uvicorn is running.")
                except Exception as e:
                    import streamlit.runtime.scriptrunner as _sr
                    if isinstance(e, _sr.StopException) or "RerunData" in type(e).__name__ or "RerunException" in type(e).__name__:
                        raise
                    st.error(f"Error: {e}")


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

    # ── Step 1: Input form (shown when no job is running) ─────────────────
    if not st.session_state.bulk_job_id:
        with st.form("bulk_form"):
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

            col_submit, col_hint = st.columns([1, 2])
            with col_submit:
                submitted = st.form_submit_button("Start Bulk Generation", type="primary")
            with col_hint:
                st.caption("The job runs in the background — you'll see live progress below.")

        # ── Handle form submission ─────────────────────────────────────────
        if submitted:
            if not bulk_prompt.strip():
                st.error("Please describe the poster type.")
            elif bulk_excel is None:
                st.error("Please upload an Excel file.")
            else:
                with st.spinner("Validating and queuing job…"):
                    files = {
                        "excel_file": (
                            bulk_excel.name,
                            bulk_excel.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ),
                    }
                    if bulk_photo:
                        files["photo"] = (bulk_photo.name, bulk_photo.getvalue(), bulk_photo.type)

                    _do_rerun = False
                    try:
                        res = requests.post(
                            f"{API}/bulk",
                            data={"prompt": bulk_prompt.strip()},
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
                            _do_rerun = True   # rerun AFTER try-except exits

                        elif res.status_code == 422:
                            st.error("❌ Excel validation failed:")
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
                        st.error(f"Error: {exc}")

                    if _do_rerun:
                        st.rerun()

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