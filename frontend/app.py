import streamlit as st
import requests
import pandas as pd
import io
import os
import time
import json
import base64
import sys

sys.path.insert(0, "backend")

API = "http://localhost:8000"

st.set_page_config(
    page_title="MS Fincap Template Generator",
    layout="centered"
)

st.title("MS Fincap AI Template Generator")
st.caption(
    "Match visual templates via RAG, extract content using AI, "
    "render final posters."
)

# ── Session state ──────────────────────────────────────────────────────
for key, default in [
    ("selected_folder", None),
    ("selected_template_id", None),
    ("extra_fields", {}),
    ("auto_generate", False),
    ("last_prompt", ""),
    # FIX: these three now hold the *result* of a successful generation.
    # They are separate from selected_folder/selected_template_id (which
    # only reflect an in-progress user choice) so the poster + style editor
    # keep rendering across reruns caused by widget interactions inside the
    # style editor itself (font dropdown, color picker, etc).
    ("last_poster_bytes", None),
    ("last_overlay_values", {}),
    ("last_folder", None),
    ("last_template_id", None),
    # FIX: holds the ambiguous/gallery/needs_input JSON response so its
    # buttons/form can be rendered UNCONDITIONALLY on every script run.
    # Previously these were rendered only inside `if should_run:`, which is
    # only True on the exact rerun that fired the API call — so clicking a
    # gallery button or submitting the missing-fields form (which triggers
    # a fresh rerun where should_run is False again) never even reached the
    # widget declaration, and the click was silently lost.
    ("pending_response", None),
    ("bulk_folder", None),
    ("bulk_template_id", None),
    # FIX: persist the *completed* job so the ZIP download and the new
    # Preview & Restyle section survive reruns triggered by widgets inside
    # that section itself (emp_id picker, font/color controls, etc) — same
    # class of bug as the single-poster tab had.
    ("bulk_done_job_id", None),
    ("bulk_done_total", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def show_image(image_bytes):
    """
    Version-safe image display. Newer Streamlit uses use_container_width;
    older installs (like the one throwing the TypeError here) only accept
    use_column_width. Try the modern kwarg first, fall back automatically.
    """
    try:
        st.image(image_bytes, use_container_width=True)
    except TypeError:
        st.image(image_bytes, use_column_width=True)


def reset_single():
    st.session_state.selected_folder = None
    st.session_state.selected_template_id = None
    st.session_state.extra_fields = {}
    st.session_state.auto_generate = False
    st.session_state.last_prompt = ""


def clear_result():
    st.session_state.last_poster_bytes = None
    st.session_state.last_overlay_values = {}
    st.session_state.last_folder = None
    st.session_state.last_template_id = None


def call_generate_api(prompt, photo=None):
    data = {"prompt": prompt}
    if st.session_state.selected_folder:
        data["folder"] = st.session_state.selected_folder
    if st.session_state.selected_template_id:
        data["template_id"] = st.session_state.selected_template_id
    if st.session_state.extra_fields:
        data["extra_fields"] = json.dumps(st.session_state.extra_fields)
    files = {}
    if photo:
        files["image"] = (photo.name, photo.getvalue(), photo.type)
    print(
        f"[frontend] POST /generate prompt={prompt!r} "
        f"folder={data.get('folder')!r} template_id={data.get('template_id')!r}"
    )
    return requests.post(
        f"{API}/generate",
        data=data,
        files=files if files else None,
        timeout=60
    )


def show_live_preview_editor(
    poster_bytes: bytes,
    folder: str,
    template_id: str,
    overlay_values: dict,
    tab_key: str = "single"
):
    show_image(poster_bytes)
    st.caption(f"folder=`{folder}` · template_id=`{template_id}`")
    st.download_button(
        "Download poster",
        poster_bytes,
        "poster.png",
        "image/png",
        key=f"dl_{tab_key}"
    )

    if not folder or not template_id:
        st.info(
            "Style editing isn't available for this poster "
            "(missing folder/template reference)."
        )
        return

    with st.expander("Edit styles — live preview", expanded=False):
        try:
            tmpl_res = requests.get(
                f"{API}/template-info",
                params={"folder": folder, "template_id": template_id},
                timeout=10
            )
            if tmpl_res.status_code != 200:
                st.warning(
                    f"Could not load template fields "
                    f"(folder=`{folder}`, template_id=`{template_id}`): "
                    f"HTTP {tmpl_res.status_code} — {tmpl_res.text}"
                )
                return
            template = tmpl_res.json()
        except Exception as e:
            st.warning(f"Backend not reachable for style editing: {e}")
            return

        text_layers = [
            l for l in template.get("overlay_layers", [])
            if l["type"] == "text"
        ]

        if not text_layers:
            st.info("No text fields to edit.")
            return

        overrides = {}
        num_cols = min(len(text_layers), 2)
        cols = st.columns(num_cols)

        for i, layer in enumerate(text_layers):
            fid = layer["id"]
            style = layer.get("style", {})
            with cols[i % num_cols]:
                st.markdown(f"**{fid.replace('_', ' ').title()}**")
                font_options = ["Poppins", "NotoSans", "NotoSansDevanagari"]
                weight_options = ["bold", "normal", "semibold"]
                align_options = ["center", "left", "right"]
                overrides[fid] = {
                    "field_id": fid,
                    "font_family": st.selectbox(
                        "Font",
                        font_options,
                        index=font_options.index(
                            style.get("font_family", "Poppins")
                        ) if style.get("font_family", "Poppins") in font_options else 0,
                        key=f"pff_{tab_key}_{fid}"
                    ),
                    "font_size": st.number_input(
                        "Size",
                        min_value=8,
                        max_value=200,
                        value=style.get("font_size", 48),
                        key=f"pfs_{tab_key}_{fid}"
                    ),
                    "font_weight": st.selectbox(
                        "Weight",
                        weight_options,
                        index=weight_options.index(
                            style.get("font_weight", "bold")
                        ) if style.get("font_weight", "bold") in weight_options else 0,
                        key=f"pfw_{tab_key}_{fid}"
                    ),
                    "color": st.color_picker(
                        "Color",
                        style.get("color", "#FFFFFF"),
                        key=f"pfc_{tab_key}_{fid}"
                    ),
                    "align": st.selectbox(
                        "Align",
                        align_options,
                        index=align_options.index(
                            style.get("align", "center")
                        ) if style.get("align", "center") in align_options else 0,
                        key=f"pfa_{tab_key}_{fid}"
                    ),
                }

        if st.button(
            "Re-render with these styles",
            type="primary",
            key=f"rerender_{tab_key}"
        ):
            with st.spinner("Re-rendering..."):
                try:
                    res = requests.post(
                        f"{API}/rerender",
                        json={
                            "folder": folder,
                            "template_id": template_id,
                            "overlay_values": overlay_values,
                            "style_overrides": list(overrides.values())
                        },
                        timeout=30
                    )
                    if res.headers.get(
                        "content-type", ""
                    ).startswith("image"):
                        st.success("Re-rendered!")
                        show_image(res.content)
                        st.download_button(
                            "Download this version",
                            res.content,
                            "poster_edited.png",
                            "image/png",
                            key=f"dl_edited_{tab_key}"
                        )
                    else:
                        st.error(f"Re-render failed: {res.text}")
                except Exception as e:
                    st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(
    ["Single Poster Generation", "Excel Bulk Generation"]
)


# ══════════════════════════════════════════════════════════════════════
# TAB 1 — SINGLE
# ══════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Generate a single poster")

    prompt = st.text_area(
        "Describe what you need",
        placeholder='e.g. "Holi poster for Rahul Kumar"',
        height=90,
        key="single_prompt"
    )

    photo = st.file_uploader(
        "Upload photo overlay (optional)",
        type=["jpg", "jpeg", "png", "heic"],
        key="single_photo"
    )

    if (
        st.session_state.selected_folder
        and st.session_state.selected_template_id
    ):
        st.info(
            f"Template selected: `{st.session_state.selected_template_id}` "
            f"from `{st.session_state.selected_folder}`"
        )
        if st.button("Clear selection", key="clear_sel"):
            reset_single()
            st.rerun()

    # ── Determine trigger ─────────────────────────────────────────────
    button_clicked = st.button(
        "Match and Generate",
        type="primary",
        key="single_generate"
    )

    # FIX (root cause of "Template not found" and "wrong poster shown"):
    # selected_folder/selected_template_id are meant to be pinned ONLY for
    # the brief auto-resubmit that follows an ambiguous/gallery pick or a
    # missing-fields form submit (that's what auto_generate=True means).
    # Previously, a manual click of "Match and Generate" with a *new*
    # prompt would still send along whatever folder/template_id was left
    # over from an earlier turn — call_generate_api() includes them
    # unconditionally whenever they're set. That meant: (a) if that old
    # selection later became invalid, every new prompt 404'd with
    # "Template not found" regardless of what you typed, and (b) if it was
    # still valid, your new prompt silently rendered using that old
    # template instead of doing a fresh RAG search. A manual click is
    # always a fresh request, so it must not inherit a stale pin.
    if button_clicked:
        st.session_state.selected_folder = None
        st.session_state.selected_template_id = None

    should_run = button_clicked or st.session_state.auto_generate
    if st.session_state.auto_generate:
        st.session_state.auto_generate = False

    if should_run:
        active_prompt = (
            prompt.strip() or st.session_state.last_prompt
        )
        if not active_prompt:
            st.warning("Please describe what you need.")
        else:
            st.session_state.last_prompt = active_prompt
            # Clear any previous result so a fresh request doesn't show a
            # stale poster while this new one runs / if it errors out.
            clear_result()
            st.session_state.pending_response = None
            with st.spinner("Searching templates and generating..."):
                try:
                    res = call_generate_api(active_prompt, photo)

                    # ── Image returned — success ───────────────────────
                    if res.headers.get(
                        "content-type", ""
                    ).startswith("image"):
                        # FIX: persist the result into session_state instead
                        # of only holding it in a local variable. Local
                        # variables from this run are gone on the very next
                        # rerun (e.g. touching a widget in the style editor
                        # below), which is why the poster used to vanish.
                        st.session_state.last_poster_bytes = res.content
                        st.session_state.last_folder = (
                            res.headers.get("X-Folder")
                            or st.session_state.selected_folder
                        )
                        st.session_state.last_template_id = (
                            res.headers.get("X-Template-Id")
                            or st.session_state.selected_template_id
                        )

                        # FIX: use the fully-resolved overlay_values the
                        # backend actually rendered with (LLM-filled fields
                        # included), not just whatever the user manually
                        # typed into a missing-fields form. Without this,
                        # /rerender would blank out any field the LLM
                        # generated on its own.
                        overlay_b64 = res.headers.get("X-Overlay-Values-B64")
                        if overlay_b64:
                            try:
                                overlay_json = base64.b64decode(
                                    overlay_b64
                                ).decode("utf-8")
                                st.session_state.last_overlay_values = (
                                    json.loads(overlay_json)
                                )
                            except Exception:
                                st.session_state.last_overlay_values = dict(
                                    st.session_state.extra_fields or {}
                                )
                        else:
                            st.session_state.last_overlay_values = dict(
                                st.session_state.extra_fields or {}
                            )

                        reset_single()

                    else:
                        resp = res.json()
                        # FIX: just persist — rendering happens below,
                        # unconditionally, so buttons/forms survive reruns.
                        st.session_state.pending_response = resp

                except requests.exceptions.ConnectionError:
                    st.error(
                        "Cannot connect to backend. "
                        "Run: uvicorn backend.main:app --reload"
                    )
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Render any pending ambiguous/gallery/needs_input result. This is
    # OUTSIDE the `if should_run:` gate on purpose (see FIX note above) so
    # the buttons/form here are re-declared — and can register clicks —
    # on every single rerun, not just the one that produced them. ────────
    if st.session_state.pending_response:
        resp = st.session_state.pending_response
        status = resp.get("status")

        if status == "no_match":
            st.error("No matching template found.")
            st.info(
                "Try a more specific description, "
                "or create a new template from the sidebar."
            )
            if st.button("Dismiss", key="dismiss_no_match"):
                st.session_state.pending_response = None
                st.rerun()

        elif status == "ambiguous":
            st.warning("Which category did you mean?")
            matches = resp.get("matches", [])
            cols = st.columns(max(len(matches), 1))
            for i, m in enumerate(matches):
                with cols[i]:
                    if st.button(
                        m["display_name"],
                        key=f"amb_{m['folder']}",
                        use_container_width=True
                    ):
                        st.session_state.selected_folder = m["folder"]
                        st.session_state.pending_response = None
                        st.session_state.auto_generate = True
                        st.rerun()

        elif status == "gallery":
            st.info(
                f"Found **{resp['display_name']}** "
                f"templates. Which design?"
            )
            for t in resp.get("templates", []):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(
                        f"**{t['template_id']}** "
                        f"— {t['description']}"
                    )
                with c2:
                    if st.button(
                        "Use this",
                        key=f"gal_{t['template_id']}",
                        use_container_width=True
                    ):
                        st.session_state.selected_folder = resp["folder"]
                        st.session_state.selected_template_id = (
                            t["template_id"]
                        )
                        st.session_state.pending_response = None
                        st.session_state.auto_generate = True
                        st.rerun()

        elif status == "needs_input":
            st.warning("A few more details needed.")
            st.session_state.selected_folder = resp.get("folder")
            st.session_state.selected_template_id = resp.get("template_id")

            with st.form("missing_fields_form"):
                st.write("Fill in the missing fields:")
                vals = {}
                for fid in resp.get("missing_fields", []):
                    vals[fid] = st.text_input(
                        fid.replace("_", " ").title(),
                        placeholder=f"Enter {fid}",
                        key=f"mf_{fid}"
                    )
                submitted = st.form_submit_button(
                    "Generate poster", type="primary"
                )

            if submitted:
                filled = {
                    k: v for k, v in vals.items()
                    if v and v.strip()
                }
                if not filled:
                    st.error("Please fill in at least one field.")
                else:
                    st.session_state.extra_fields = filled
                    st.session_state.pending_response = None
                    st.session_state.auto_generate = True
                    st.rerun()

        elif status == "column_mismatch":
            st.error(resp.get("message", "Column mismatch"))
            if st.button("Dismiss", key="dismiss_col_mismatch"):
                st.session_state.pending_response = None
                st.rerun()

        else:
            st.error(f"Unexpected: {resp}")
            if st.button("Dismiss", key="dismiss_unexpected"):
                st.session_state.pending_response = None
                st.rerun()

    # ── FIX: render the last successful result on EVERY script run, not
    # just the run where it was generated. This is what makes the poster
    # and the live-preview/style editor survive reruns triggered by
    # widgets inside the editor itself (font choice, color picker, etc). ──
    if st.session_state.last_poster_bytes:
        st.success("Poster generated!")
        show_live_preview_editor(
            st.session_state.last_poster_bytes,
            st.session_state.last_folder,
            st.session_state.last_template_id,
            st.session_state.last_overlay_values,
            tab_key="single"
        )
        if st.button("Generate a different poster", key="clear_result"):
            clear_result()
            st.rerun()


# ══════════════════════════════════════════════════════════════════════
# TAB 2 — BULK
# ══════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Generate posters for multiple people from Excel")

    bulk_prompt = st.text_area(
        "Describe the poster",
        placeholder='e.g. "Holi greeting poster for all employees"',
        height=80,
        key="bulk_prompt"
    )

    excel_file = st.file_uploader(
        "Upload Excel (.xlsx or .csv)",
        type=["xlsx", "xls", "csv"],
        help=(
            "Must contain emp_id column. "
            "All overlay field IDs must match column names exactly."
        ),
        key="bulk_excel"
    )

    if excel_file is not None:
        try:
            raw = excel_file.read()
            excel_file.seek(0)
            if excel_file.name.endswith(".csv"):
                df_prev = pd.read_csv(io.BytesIO(raw))
            else:
                df_prev = pd.read_excel(io.BytesIO(raw))
            st.success(
                f"Loaded: {len(df_prev)} rows | "
                f"Columns: {', '.join(df_prev.columns.tolist())}"
            )
            st.dataframe(df_prev.head(3), use_container_width=True)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            excel_file = None

    if st.button(
        "Generate Posters",
        type="primary",
        disabled=not (bulk_prompt.strip() and excel_file is not None),
        key="bulk_generate"
    ):
        with st.spinner("Validating and queuing job..."):
            try:
                excel_file.seek(0)
                excel_bytes = excel_file.read()
                mime = (
                    "text/csv"
                    if excel_file.name.endswith(".csv")
                    else (
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet"
                    )
                )
                form_data = {"prompt": bulk_prompt}
                if st.session_state.bulk_folder:
                    form_data["folder"] = st.session_state.bulk_folder
                if st.session_state.bulk_template_id:
                    form_data["template_id"] = (
                        st.session_state.bulk_template_id
                    )

                res = requests.post(
                    f"{API}/bulk",
                    data=form_data,
                    files={"excel": (excel_file.name, excel_bytes, mime)},
                    timeout=30
                )
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to backend.")
                st.stop()
            except Exception as e:
                st.error(f"Request failed: {e}")
                st.stop()

        if res.status_code == 422:
            st.error(res.json().get("detail", "Validation error."))
            st.stop()

        data = res.json()
        status = data.get("status")

        if status == "no_match":
            st.error("No matching template found.")

        elif status == "ambiguous":
            st.warning("Which category?")
            for m in data.get("matches", []):
                if st.button(
                    m["display_name"],
                    key=f"bamb_{m['folder']}"
                ):
                    st.session_state.bulk_folder = m["folder"]
                    st.rerun()

        elif status == "gallery":
            st.info(f"Which {data['display_name']} design for the batch?")
            for t in data.get("templates", []):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(
                        f"**{t['template_id']}** — {t['description']}"
                    )
                with c2:
                    if st.button(
                        "Use this",
                        key=f"bgal_{t['template_id']}"
                    ):
                        st.session_state.bulk_folder = data["folder"]
                        st.session_state.bulk_template_id = (
                            t["template_id"]
                        )
                        st.rerun()

        elif status == "column_mismatch":
            st.error(data.get("message", "Column mismatch."))
            missing = data.get("missing_required_columns", [])
            if missing:
                st.write("**Add these columns to your Excel:**")
                for col in missing:
                    st.code(col)
            required = data.get("required_columns", [])
            buf = io.BytesIO()
            pd.DataFrame(columns=required).to_excel(buf, index=False)
            buf.seek(0)
            st.download_button(
                "Download correct Excel template",
                buf,
                "correct_template.xlsx",
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            )

        elif status == "queued":
            job_id = data["job_id"]
            total = data["total_rows"]
            st.success(f"Job started — {total} rows queued.")
            progress_bar = st.progress(0)
            status_text = st.empty()

            while True:
                try:
                    jr = requests.get(
                        f"{API}/job-status/{job_id}", timeout=10
                    )
                    job = jr.json()
                except Exception:
                    status_text.warning("Connection lost — retrying...")
                    time.sleep(3)
                    continue

                done = job.get("completed", 0)
                skip = job.get("skipped", 0)
                fail = job.get("failed", 0)
                tot = job.get("total", total)
                prog = done / tot if tot > 0 else 0
                progress_bar.progress(min(prog, 1.0))
                status_text.write(
                    f"{done}/{tot} done · {skip} skipped · {fail} failed"
                )

                if job.get("status") == "done":
                    progress_bar.progress(1.0)
                    status_text.empty()
                    # FIX: persist to session_state and let the section
                    # below render the summary/download/restyle UI on every
                    # rerun, instead of doing it here inline (which only
                    # ever ran once, inside this button's block, and would
                    # vanish the instant any restyle widget was touched).
                    st.session_state.bulk_done_job_id = job_id
                    st.session_state.bulk_done_total = tot
                    st.session_state.bulk_folder = None
                    st.session_state.bulk_template_id = None
                    break

                time.sleep(2)
        else:
            st.error(f"Unexpected: {data}")

# ── Bulk job summary, download, and restyle — rendered unconditionally so
# it survives reruns caused by widgets inside the restyle controls. ──────
with tab2:
    if st.session_state.bulk_done_job_id:
        job_id = st.session_state.bulk_done_job_id
        try:
            jr = requests.get(f"{API}/job-status/{job_id}", timeout=10)
            job = jr.json() if jr.status_code == 200 else None
        except Exception:
            job = None

        if not job:
            st.warning("Could not load job status.")
        else:
            done = job.get("completed", 0)
            skip = job.get("skipped", 0)
            fail = job.get("failed", 0)
            st.divider()
            st.success(
                f"Last batch complete — {done} posters, "
                f"{skip} skipped, {fail} failed"
            )
            if skip > 0:
                st.warning(
                    f"{skip} rows skipped — blank required fields. "
                    f"See skipped.json in the ZIP."
                )

            zip_path = job.get("zip_path", "")
            if zip_path and os.path.exists(zip_path):
                with open(zip_path, "rb") as zf:
                    st.download_button(
                        "Download ZIP",
                        zf.read(),
                        f"posters_{job_id[:8]}.zip",
                        "application/zip",
                        key="bulk_download_zip"
                    )
            else:
                st.error("ZIP not found. Check output/ folder.")

            if done > 0:
                with st.expander("Preview and restyle", expanded=False):
                    try:
                        info_res = requests.get(
                            f"{API}/bulk-preview-info/{job_id}", timeout=10
                        )
                        info = (
                            info_res.json()
                            if info_res.status_code == 200 else None
                        )
                    except Exception:
                        info = None

                    if not info or not info.get("emp_ids"):
                        st.info(
                            "No preview data available for this batch "
                            "(it may predate the restyle feature)."
                        )
                    else:
                        b_folder = info["folder"]
                        b_template_id = info["template_id"]

                        picked_emp = st.selectbox(
                            "Preview a poster",
                            info["emp_ids"],
                            key="bulk_preview_emp"
                        )

                        try:
                            poster_res = requests.get(
                                f"{API}/bulk-poster/{job_id}/{picked_emp}",
                                timeout=15
                            )
                            if poster_res.status_code == 200:
                                show_image(poster_res.content)
                            else:
                                st.warning(
                                    f"Could not load poster for {picked_emp}."
                                )
                        except Exception as e:
                            st.warning(f"Could not load poster: {e}")

                        try:
                            tmpl_res = requests.get(
                                f"{API}/template-info",
                                params={
                                    "folder": b_folder,
                                    "template_id": b_template_id
                                },
                                timeout=10
                            )
                            template = (
                                tmpl_res.json()
                                if tmpl_res.status_code == 200 else None
                            )
                        except Exception:
                            template = None

                        if not template:
                            st.warning(
                                "Could not load template fields for restyling "
                                f"(folder=`{b_folder}`, "
                                f"template_id=`{b_template_id}`)."
                            )
                        else:
                            text_layers = [
                                l for l in template.get("overlay_layers", [])
                                if l["type"] == "text"
                            ]
                            if not text_layers:
                                st.info("No text fields to restyle.")
                            else:
                                overrides = {}
                                num_cols = min(len(text_layers), 2)
                                cols = st.columns(num_cols)

                                for i, layer in enumerate(text_layers):
                                    fid = layer["id"]
                                    style = layer.get("style", {})
                                    with cols[i % num_cols]:
                                        st.markdown(
                                            f"**{fid.replace('_', ' ').title()}**"
                                        )
                                        font_options = [
                                            "Poppins", "NotoSans",
                                            "NotoSansDevanagari"
                                        ]
                                        weight_options = [
                                            "bold", "normal", "semibold"
                                        ]
                                        align_options = [
                                            "center", "left", "right"
                                        ]
                                        overrides[fid] = {
                                            "field_id": fid,
                                            "font_family": st.selectbox(
                                                "Font", font_options,
                                                index=font_options.index(
                                                    style.get(
                                                        "font_family",
                                                        "Poppins"
                                                    )
                                                ) if style.get(
                                                    "font_family", "Poppins"
                                                ) in font_options else 0,
                                                key=f"bpff_{fid}"
                                            ),
                                            "font_size": st.number_input(
                                                "Size", min_value=8,
                                                max_value=200,
                                                value=style.get(
                                                    "font_size", 48
                                                ),
                                                key=f"bpfs_{fid}"
                                            ),
                                            "font_weight": st.selectbox(
                                                "Weight", weight_options,
                                                index=weight_options.index(
                                                    style.get(
                                                        "font_weight", "bold"
                                                    )
                                                ) if style.get(
                                                    "font_weight", "bold"
                                                ) in weight_options else 0,
                                                key=f"bpfw_{fid}"
                                            ),
                                            "color": st.color_picker(
                                                "Color",
                                                style.get("color", "#FFFFFF"),
                                                key=f"bpfc_{fid}"
                                            ),
                                            "align": st.selectbox(
                                                "Align", align_options,
                                                index=align_options.index(
                                                    style.get(
                                                        "align", "center"
                                                    )
                                                ) if style.get(
                                                    "align", "center"
                                                ) in align_options else 0,
                                                key=f"bpfa_{fid}"
                                            ),
                                        }

                                if st.button(
                                    "Apply to all posters in this batch",
                                    type="primary",
                                    key="bulk_restyle_apply"
                                ):
                                    with st.spinner(
                                        "Re-rendering entire batch..."
                                    ):
                                        try:
                                            rs_res = requests.post(
                                                f"{API}/bulk-restyle",
                                                json={
                                                    "job_id": job_id,
                                                    "style_overrides": list(
                                                        overrides.values()
                                                    )
                                                },
                                                timeout=120
                                            )
                                            if rs_res.headers.get(
                                                "content-type", ""
                                            ) == "application/zip":
                                                st.success(
                                                    "Batch re-rendered!"
                                                )
                                                st.download_button(
                                                    "Download restyled ZIP",
                                                    rs_res.content,
                                                    "posters_restyled.zip",
                                                    "application/zip",
                                                    key="bulk_restyle_download"
                                                )
                                            else:
                                                st.error(
                                                    f"Restyle failed: "
                                                    f"{rs_res.text}"
                                                )
                                        except Exception as e:
                                            st.error(f"Error: {e}")