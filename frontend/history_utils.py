import streamlit as st
import requests
import os
from auth_utils import get_auth_headers

BACKEND_URL = "http://127.0.0.1:8000"


def render_history_sidebar():
    headers = get_auth_headers()
    if not headers:
        return

    st.sidebar.markdown("---")
    st.sidebar.subheader("🗂️ Project History")

    # Display Logged In info
    st.sidebar.markdown(
        f"""
        <div style='background-color: #F3F4F6; padding: 0.5rem; border-radius: 4px; margin-bottom: 1rem;'>
            <small style='color: #4B5563;'>Signed in as:</small><br/>
            <b>{st.session_state.get('user_name', 'User')}</b> ({st.session_state.get('user_role', 'user')})
        </div>
        """,
        unsafe_allow_html=True
    )

    # Logout button
    if st.sidebar.button("🚪 Log Out", use_container_width=True):
        st.session_state.jwt_token = None
        st.session_state.user_email = None
        st.session_state.user_name = None
        st.session_state.user_role = None
        st.session_state.selected_conversation_id = None
        # Clean page session states too
        st.session_state.ca_thread_id = None
        st.session_state.ca_started = False
        st.session_state.ca_messages = []
        st.rerun()

    try:
        response = requests.get(f"{BACKEND_URL}/history/conversations", headers=headers)
        if response.status_code == 200:
            conversations = response.json()
            if not conversations:
                st.sidebar.info("No past projects yet.")
                return

            if "selected_conversation_id" not in st.session_state:
                st.session_state.selected_conversation_id = None

            conv_id = st.session_state.selected_conversation_id

            # Render Active Conversation details at top if selected
            if conv_id:
                det_resp = requests.get(f"{BACKEND_URL}/history/conversations/{conv_id}/messages", headers=headers)
                if det_resp.status_code == 200:
                    data = det_resp.json()
                    conv_type = data["conversation"]["conversation_type"]
                    title_display = data['conversation']['title']
                    if len(title_display) > 30:
                        title_display = title_display[:30] + "..."
                    
                    with st.sidebar.expander(f"📌 Active: {title_display}", expanded=True):
                        st.caption(f"Type: `{conv_type.upper()}`")
                        
                        # Display conversation messages (User Prompt + Assistant Response convo)
                        st.markdown("**Conversation:**")
                        for m in data.get("messages", []):
                            if m["role"] == "user":
                                st.markdown(f"💬 **You:** {m['content']}")
                            else:
                                st.markdown(f"🤖 **Assistant:** {m['content']}")

                        if conv_type == "bulk":
                            status = data["conversation"]["job_status"] or "unknown"
                            st.write(f"**Status:** `{status.upper()}` ({data['conversation']['job_completed']}/{data['conversation']['job_total']})")
                            if status == "done":
                                try:
                                    zip_resp = requests.get(f"{BACKEND_URL}/download/{conv_id}", headers=headers)
                                    if zip_resp.status_code == 200:
                                        st.download_button(
                                            label="📥 Download ZIP File",
                                            data=zip_resp.content,
                                            file_name=f"bulk_posters_{conv_id[:8]}.zip",
                                            mime="application/zip",
                                            use_container_width=True
                                        )
                                except Exception as dl_err:
                                    st.error(f"Download error: {dl_err}")

                        elif conv_type == "creation_agent":
                            st.success("Session auto-loaded! Ready on 'Create Template' page.")

                        elif conv_type == "single":
                            last_img_path = None
                            for m in reversed(data.get("messages", [])):
                                if m["role"] == "assistant" and m.get("output_file_path"):
                                    last_img_path = m["output_file_path"]
                                    break

                            if last_img_path:
                                try:
                                    img_resp = requests.get(
                                        f"{BACKEND_URL}/history/conversations/{conv_id}/image",
                                        headers=headers
                                    )
                                    if img_resp.status_code == 200:
                                        st.image(
                                            img_resp.content,
                                            caption="Generated Poster",
                                            use_column_width=True
                                        )
                                        st.download_button(
                                            label="📥 Download PNG",
                                            data=img_resp.content,
                                            file_name=f"poster_{conv_id[:8]}.png",
                                            mime="image/png",
                                            use_container_width=True
                                        )
                                except Exception as img_err:
                                    st.error(f"Image load error: {img_err}")

            st.sidebar.write("Recent Sessions:")

            for conv in conversations:
                label = f"[{conv['conversation_type'].upper()}] {conv['title']}"
                if st.sidebar.button(label, key=f"conv_btn_{conv['id']}", use_container_width=True):
                    st.session_state.selected_conversation_id = conv["id"]
                    
                    # Auto-resume creation_agent session immediately
                    if conv["conversation_type"] == "creation_agent":
                        det_resp = requests.get(f"{BACKEND_URL}/history/conversations/{conv['id']}/messages", headers=headers)
                        if det_resp.status_code == 200:
                            data = det_resp.json()
                            st.session_state.ca_thread_id = conv["id"]
                            st.session_state.ca_started = True
                            st.session_state.ca_messages = [
                                {"role": m["role"], "content": m["content"]} for m in data.get("messages", [])
                            ]
                            st.session_state.ca_step = "chat"
                            try:
                                state_resp = requests.get(
                                    f"{BACKEND_URL}/agent/conversations/{conv['id']}/state",
                                    headers=headers
                                )
                                if state_resp.status_code == 200:
                                    state = state_resp.json()
                                    st.session_state.ca_assumptions = state.get("assumptions", {})
                                    st.session_state.ca_ready = bool(state.get("generated_prompt", ""))
                                    for k, v in state.get("assumptions", {}).items():
                                        st.session_state[f"ca_ass_val_{k}"] = v or ""
                                    st.session_state["ca_prompt_textarea"] = state.get("generated_prompt", "") or ""
                            except Exception:
                                pass
                    st.rerun()

        else:
            st.sidebar.error("Failed to load history.")
    except Exception as e:
        import streamlit.runtime.scriptrunner as _sr
        if isinstance(e, _sr.StopException) or "Rerun" in type(e).__name__:
            raise e
        st.sidebar.error(f"Error loading history: {e}")