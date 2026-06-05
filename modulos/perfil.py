import streamlit as st

from services.auth import current_user, verify_password
from services.db import require_db, table
from services.ui import header


def _get_usuario_actual(db, user_id):
    res = db.table(table("usuarios")).select("*").eq("id", user_id).execute()
    data = res.data or []
    return data[0] if data else None


def render():
    user = current_user() or {}
    user_id = user.get("id")

    header("🙋 Mi perfil", "Datos de la cuenta y cambio de contraseña")

    if not user_id:
        st.error("No pude identificar el usuario actual. Cerrá sesión y volvé a entrar.")
        st.stop()

    db = require_db()
    usuario_db = _get_usuario_actual(db, user_id)

    if not usuario_db:
        st.error("No encontré tu usuario en la base de datos.")
        st.stop()

    c1, c2, c3 = st.columns(3)
    c1.info(f"Usuario: {usuario_db.get('usuario')}")
    c2.info(f"Rol: {usuario_db.get('rol')}")
    c3.info("Activo: Sí" if usuario_db.get("activo", True) else "Activo: No")

    st.divider()
    st.subheader("Cambiar contraseña")

    with st.form("cambiar_clave"):
        clave_actual = st.text_input("Contraseña actual", type="password")
        nueva_clave = st.text_input("Nueva contraseña", type="password")
        repetir_clave = st.text_input("Confirmar nueva contraseña", type="password")

        guardar = st.form_submit_button("Guardar nueva contraseña")

        if guardar:
            if not clave_actual or not nueva_clave or not repetir_clave:
                st.warning("Completá todos los campos.")
            elif not verify_password(clave_actual, usuario_db.get("clave")):
                st.error("La contraseña actual no es correcta.")
            elif nueva_clave != repetir_clave:
                st.error("La nueva contraseña y la confirmación no coinciden.")
            elif len(nueva_clave) < 4:
                st.warning("La nueva contraseña debe tener al menos 4 caracteres.")
            else:
                db.table(table("usuarios")).update({"clave": nueva_clave}).eq("id", user_id).execute()
                st.success("Contraseña actualizada correctamente.")
                st.info("La próxima vez ingresá con la nueva contraseña.")
