import streamlit as st
import requests
import os

API = "http://localhost:8000"

st.set_page_config(page_title="MS Fincap Template Generator", layout="centered")
st.title("MS Fincap Template Generator")

if "selected_folder" not in st.session_state:
    st.session_state.selected_folder = None
if "selected_template_id" not in st.session_state:
    st.session_state.selected_template_id = None
if "extra_fields" not in st.session_state:
    st.session_state.extra_fields = {}

prompt = st.text_area("What poster do you need?",
    placeholder="Holi poster for Rahul Kumar",
    height=80)

photo = st.file_uploader("Upload profile photo (optional)", type=["jpg", "jpeg", "png", "heic"])

if st.button("Generate poster", type="primary"):
    if not prompt.strip():
        st.warning("Please describe what you need.")
    else:
        with st.spinner("Finding the right template..."):
            data = {"prompt": prompt}
            if st.session_state.selected_folder:
                data["folder"] = st.session_state.selected_folder
            if st.session_state.selected_template_id:
                data["template_id"] = st.session_state.selected_template_id
            for k, v in st.session_state.extra_fields.items():
                data[k] = v

            files = {}
            if photo:
                files["image"] = (photo.name, photo.getvalue(), photo.type)

            try:
                res = requests.post(f"{API}/generate", data=data, files=files or None, timeout=60)

                if res.headers.get("content-type", "").startswith("image"):
                    st.success("Poster generated!")
                    st.image(res.content)
                    st.download_button("Download poster", res.content,
                        "poster.png", "image/png")
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
                                    placeholder=f"Enter {fid}"
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
                st.error(f"Error: {e}")