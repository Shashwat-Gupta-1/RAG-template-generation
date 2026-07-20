import streamlit as st
import requests

BACKEND_URL = "http://127.0.0.1:8000"

def get_auth_headers():
    if "jwt_token" in st.session_state and st.session_state.jwt_token:
        return {"Authorization": f"Bearer {st.session_state.jwt_token}"}
    return {}

def login_user(email, password):
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.jwt_token = data["access_token"]
            st.session_state.user_email = email
            # Fetch user info
            me_resp = requests.get(
                f"{BACKEND_URL}/auth/me",
                headers={"Authorization": f"Bearer {data['access_token']}"}
            )
            if me_resp.status_code == 200:
                st.session_state.user_name = me_resp.json()["name"]
                st.session_state.user_role = me_resp.json()["role"]
            return True, "Login successful!"
        else:
            detail = response.json().get("detail", "Invalid email or password.")
            return False, detail
    except Exception as e:
        return False, f"Failed to connect to backend: {e}"

def register_user(email, name, password):
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/register",
            json={"email": email, "name": name, "password": password}
        )
        if response.status_code == 200:
            return True, "Registration successful! Please log in."
        else:
            detail = response.json().get("detail", "Registration failed.")
            return False, detail
    except Exception as e:
        return False, f"Failed to connect to backend: {e}"

def auth_gate():
    if "jwt_token" not in st.session_state or not st.session_state.jwt_token:
        st.markdown(
            """
            <div style='text-align: center; padding: 2rem 0;'>
                <h1 style='color: #1E3A8A; font-family: "Outfit", sans-serif;'>MS Fincap Creative Studio</h1>
                <p style='color: #6B7280;'>Log in or register to start generating premium branding templates.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab1, tab2 = st.tabs(["🔒 Log In", "📝 Register"])

        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email Address", key="login_email")
                password = st.text_input("Password", type="password", key="login_pwd")
                submit = st.form_submit_button("Sign In", use_container_width=True)
                
                if submit:
                    if not email or not password:
                        st.error("Please fill in all fields.")
                    else:
                        success, msg = login_user(email, password)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        with tab2:
            with st.form("register_form"):
                reg_name = st.text_input("Full Name", key="reg_name")
                reg_email = st.text_input("Email Address", key="reg_email")
                reg_pwd = st.text_input("Password", type="password", key="reg_pwd")
                submit = st.form_submit_button("Create Account", use_container_width=True)
                
                if submit:
                    if not reg_name or not reg_email or not reg_pwd:
                        st.error("Please fill in all fields.")
                    else:
                        success, msg = register_user(reg_email, reg_name, reg_pwd)
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
        return False
    return True
