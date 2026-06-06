import pandas as pd
import streamlit as st

from services.auth import current_user
from services.db import require_db, money
from services.ui import header


def _leer_locales(db):
    return (
        db.table("namnam_locales")
        .select("*")
        .order("id")
        .execute()
        .data
        or []
    )


def render():
    user = current_user() or {}
    rol = user.get("rol")

    if rol != "admin":
        st.error("Solo el administrador puede gestionar locales.")
        return

    header("🏪 Locales", "Puntos de retiro para pedidos online")

    db = require_db()

    tab_nuevo, tab_lista = st.tabs(["➕ Nuevo local", "🏪 Locales cargados"])

    with tab_nuevo:
        st.subheader("Agregar local / punto de retiro")

        with st.form("nuevo_local"):
            nombre = st.text_input("Nombre", placeholder="Ej: Local Bulnes 90")
            direccion = st.text_input("Dirección", placeholder="Ej: Bulnes 90")
            horarios = st.text_area(
                "Horarios de atención",
                placeholder="Ej: Lunes a viernes de 9 a 13 y 18 a 22"
            )
            activo = st.toggle("Activo", value=True)

            guardar = st.form_submit_button("Guardar local")

            if guardar:
                if not nombre.strip():
                    st.warning("Falta el nombre del local.")
                else:
                    db.table("namnam_locales").insert({
                        "nombre": nombre.strip(),
                        "direccion": direccion.strip(),
                        "horarios": horarios.strip(),
                        "activo": activo,
                    }).execute()

                    st.success("Local guardado.")
                    st.rerun()

    with tab_lista:
        st.subheader("Locales disponibles")

        try:
            locales = _leer_locales(db)
        except Exception as e:
            st.error("No pude leer locales.")
            st.exception(e)
            return

        if not locales:
            st.info("Todavía no hay locales cargados.")
            return

        for local in locales:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])

                c1.markdown(f"### 🏪 {local.get('nombre')}")
                c1.write(f"**Dirección:** {local.get('direccion') or '-'}")
                c1.caption(local.get("horarios") or "Sin horarios cargados")

                activo = c2.toggle(
                    "Activo",
                    value=bool(local.get("activo", True)),
                    key=f"local_activo_{local['id']}"
                )

                if activo != bool(local.get("activo", True)):
                    db.table("namnam_locales").update({
                        "activo": activo
                    }).eq("id", local["id"]).execute()
                    st.rerun()

                with st.expander("Editar local"):
                    nuevo_nombre = st.text_input(
                        "Nombre",
                        value=local.get("nombre") or "",
                        key=f"local_nombre_{local['id']}"
                    )
                    nueva_direccion = st.text_input(
                        "Dirección",
                        value=local.get("direccion") or "",
                        key=f"local_dir_{local['id']}"
                    )
                    nuevos_horarios = st.text_area(
                        "Horarios",
                        value=local.get("horarios") or "",
                        key=f"local_horarios_{local['id']}"
                    )

                    col_g, col_b = st.columns([1, 1])

                    if col_g.button("Guardar cambios", key=f"guardar_local_{local['id']}"):
                        db.table("namnam_locales").update({
                            "nombre": nuevo_nombre.strip(),
                            "direccion": nueva_direccion.strip(),
                            "horarios": nuevos_horarios.strip(),
                            "activo": activo,
                        }).eq("id", local["id"]).execute()

                        st.success("Local actualizado.")
                        st.rerun()

                    if col_b.button("Eliminar local", key=f"borrar_local_{local['id']}"):
                        db.table("namnam_locales").delete().eq("id", local["id"]).execute()
                        st.success("Local eliminado.")
                        st.rerun()
