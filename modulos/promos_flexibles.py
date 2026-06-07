import streamlit as st

from services.auth import current_user
from services.db import require_db, fetch_table, money
from services.ui import header


def _float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _familias_productos():
    try:
        productos = [p for p in fetch_table("productos", "id") if p.get("activo")]
    except Exception:
        return ["Tartas"]

    familias = sorted({
        str(
            p.get("familia")
            or p.get("categoria")
            or p.get("categoría")
            or p.get("rubro")
            or p.get("grupo")
            or "Otros"
        ).strip()
        for p in productos
        if str(
            p.get("familia")
            or p.get("categoria")
            or p.get("categoría")
            or p.get("rubro")
            or p.get("grupo")
            or "Otros"
        ).strip()
    })

    return familias or ["Tartas"]


def _leer_promos_flex(db):
    try:
        return (
            db.table("namnam_promos_flexibles")
            .select("*")
            .order("id")
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def render():
    user = current_user() or {}
    if user.get("rol") != "admin":
        st.error("Solo el administrador puede gestionar promos flexibles.")
        return

    header("🧺 Promos flexibles", "Promos donde el cliente elige productos dentro de una familia")

    db = require_db()
    familias = _familias_productos()

    tab_nueva, tab_lista = st.tabs(["➕ Nueva promo flexible", "📋 Promos cargadas"])

    with tab_nueva:
        with st.form("nueva_promo_flexible"):
            nombre = st.text_input("Nombre", value="6 tartas $29.000")
            descripcion = st.text_area(
                "Descripción",
                value="Elegí 6 tartas comunes. No incluye tartas premium.",
            )

            familia = st.selectbox(
                "Familia incluida",
                familias,
                index=familias.index("Tartas") if "Tartas" in familias else 0,
            )

            texto_excluir = st.text_input(
                "Excluir productos que contengan este texto",
                value="premium",
            )

            cantidad = st.number_input("Cantidad requerida", min_value=1.0, step=1.0, value=6.0)
            precio = st.number_input("Precio de la promo", min_value=0.0, step=500.0, value=29000.0)
            activo = st.toggle("Activa", value=True)

            if st.form_submit_button("Guardar promo flexible"):
                if not nombre.strip():
                    st.warning("Falta el nombre.")
                else:
                    db.table("namnam_promos_flexibles").insert({
                        "nombre": nombre.strip(),
                        "descripcion": descripcion.strip(),
                        "familia_incluida": familia,
                        "texto_excluir": texto_excluir.strip().lower(),
                        "cantidad_requerida": cantidad,
                        "precio": precio,
                        "activo": activo,
                    }).execute()
                    st.success("Promo flexible guardada.")
                    st.rerun()

    with tab_lista:
        promos = _leer_promos_flex(db)

        if not promos:
            st.info("Todavía no hay promos flexibles.")
            return

        for promo in promos:
            with st.container(border=True):
                st.markdown(f"### {promo.get('nombre')}")
                st.write(f"**Familia:** {promo.get('familia_incluida')}")
                st.write(f"**Excluir:** {promo.get('texto_excluir') or '-'}")
                st.write(f"**Cantidad:** {_float(promo.get('cantidad_requerida')):g}")
                st.write(f"**Precio:** {money(promo.get('precio'))}")

                if promo.get("descripcion"):
                    st.caption(promo.get("descripcion"))

                activo = st.toggle(
                    "Activa",
                    value=bool(promo.get("activo", True)),
                    key=f"pf_activa_{promo['id']}",
                )

                with st.expander("Editar"):
                    nombre = st.text_input("Nombre", value=promo.get("nombre") or "", key=f"pf_nom_{promo['id']}")
                    descripcion = st.text_area("Descripción", value=promo.get("descripcion") or "", key=f"pf_desc_{promo['id']}")

                    familia_actual = promo.get("familia_incluida") or familias[0]
                    idx = familias.index(familia_actual) if familia_actual in familias else 0

                    familia = st.selectbox("Familia incluida", familias, index=idx, key=f"pf_fam_{promo['id']}")
                    texto_excluir = st.text_input("Excluir texto", value=promo.get("texto_excluir") or "", key=f"pf_exc_{promo['id']}")
                    cantidad = st.number_input(
                        "Cantidad requerida",
                        min_value=1.0,
                        step=1.0,
                        value=_float(promo.get("cantidad_requerida") or 1),
                        key=f"pf_cant_{promo['id']}",
                    )
                    precio = st.number_input(
                        "Precio",
                        min_value=0.0,
                        step=500.0,
                        value=_float(promo.get("precio") or 0),
                        key=f"pf_precio_{promo['id']}",
                    )

                    c1, c2 = st.columns(2)

                    if c1.button("Guardar cambios", key=f"pf_guardar_{promo['id']}"):
                        db.table("namnam_promos_flexibles").update({
                            "nombre": nombre.strip(),
                            "descripcion": descripcion.strip(),
                            "familia_incluida": familia,
                            "texto_excluir": texto_excluir.strip().lower(),
                            "cantidad_requerida": cantidad,
                            "precio": precio,
                            "activo": activo,
                        }).eq("id", promo["id"]).execute()
                        st.success("Promo actualizada.")
                        st.rerun()

                    if c2.button("Eliminar", key=f"pf_borrar_{promo['id']}"):
                        db.table("namnam_promos_flexibles").delete().eq("id", promo["id"]).execute()
                        st.success("Promo eliminada.")
                        st.rerun()
