import streamlit as st
from services.auth import current_user
from services.db import require_db, fetch_table, table
from services.ui import header

ROLES = ["admin", "mostrador", "produccion", "reparto", "caja"]


def render():
    user = current_user() or {}

    if user.get("rol") != "admin":
        st.error("Solo el administrador puede gestionar colaboradores.")
        return

    header(
        "👥 Colaboradores",
        "Alta, modificación y baja lógica de usuarios del sistema"
    )

    db = require_db()

    with st.expander("➕ Alta de colaborador", expanded=True):
        with st.form("alta_colaborador", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)

            usuario = c1.text_input("Usuario")
            clave = c2.text_input("Clave", type="password")
            rol = c3.selectbox("Rol", ROLES, index=1)

            if st.form_submit_button("Crear colaborador"):
                if not usuario.strip() or not clave.strip():
                    st.warning("Falta usuario o clave.")
                else:
                    try:
                        db.table(table("usuarios")).insert({
                            "usuario": usuario.strip(),
                            "clave": clave.strip(),
                            "rol": rol,
                            "activo": True
                        }).execute()

                        st.success("Colaborador creado.")
                        st.rerun()

                    except Exception as e:
                        st.error("No pude crear el colaborador. Puede que el usuario ya exista.")
                        st.exception(e)

    st.subheader("Listado de colaboradores")

    usuarios = fetch_table("usuarios")

    if not usuarios:
        st.info("No hay colaboradores cargados.")
        return

    for u in usuarios:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])

            usuario_edit = c1.text_input(
                "Usuario",
                u.get("usuario") or "",
                key=f"usr_{u['id']}"
            )

            rol_actual = u.get("rol") or "mostrador"
            idx = ROLES.index(rol_actual) if rol_actual in ROLES else 1

            rol_edit = c2.selectbox(
                "Rol",
                ROLES,
                index=idx,
                key=f"rol_{u['id']}"
            )

            activo_edit = c3.toggle(
                "Activo",
                value=bool(u.get("activo", True)),
                key=f"act_{u['id']}"
            )

            b1, b2 = st.columns(2)

            with b1:
                if st.button("Guardar cambios", key=f"guardar_{u['id']}"):
                    db.table(table("usuarios")).update({
                        "usuario": usuario_edit.strip(),
                        "rol": rol_edit,
                        "activo": activo_edit
                    }).eq("id", u["id"]).execute()

                    st.success("Colaborador actualizado.")
                    st.rerun()

            with b2:
                if st.button("🔑 Resetear clave", key=f"reset_{u['id']}"):
                    db.table(table("usuarios")).update({
                        "clave": "1234"
                    }).eq("id", u["id"]).execute()

                    st.success(f"Contraseña de {usuario_edit} restablecida a 1234")
                    st.rerun()
