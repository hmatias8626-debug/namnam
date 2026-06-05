import hashlib
import streamlit as st
from services.db import require_db, table


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_password(password: str, stored: str | None) -> bool:
    if stored is None:
        return False
    stored = str(stored)
    # Permite clave simple al inicio para no trabarnos. Después lo cambiamos por hash.
    if password == stored:
        return True
    if stored == _sha256(password):
        return True
    if stored.startswith("sha256$") and stored.split("$", 1)[1] == _sha256(password):
        return True
    return False


def is_logged_in() -> bool:
    return bool(st.session_state.get("namnam_user"))


def current_user() -> dict | None:
    return st.session_state.get("namnam_user")


def login_box():
    st.markdown("<div style='height:450px'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.6, 0.7, 1.6])
    with c2:
        st.markdown("<h1 style='text-align:center;color:#D89B1D;'>ÑAM ÑAM</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#FFF7E6;'>Sistema de gestión</p>", unsafe_allow_html=True)
        with st.container(border=True):
            usuario = st.text_input("Usuario")
            clave = st.text_input("Contraseña", type="password")
            entrar = st.button("Ingresar", use_container_width=True)
            if entrar:
                db = require_db()
                res = db.table(table("usuarios")).select("*").eq("usuario", usuario.strip()).eq("activo", True).execute().data
                if res and verify_password(clave, res[0].get("clave")):
                    st.session_state["namnam_user"] = {
                        "id": res[0].get("id"),
                        "usuario": res[0].get("usuario"),
                        "rol": res[0].get("rol", "admin"),
                    }
                    st.success("Ingreso correcto.")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")


def require_login():
    if not is_logged_in():
        login_box()
        st.stop()


def logout_button():
    user = current_user()
    with st.sidebar:
        if user:
            st.caption(f"Usuario: {user.get('usuario')} · Rol: {user.get('rol')}")
        if st.button("Cerrar sesión"):
            st.session_state.pop("namnam_user", None)
            st.rerun()
