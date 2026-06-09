import pandas as pd
import streamlit as st

from services.auth import current_user
from services.db import require_db, fetch_table, money, table
from services.ui import header


def _float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _familia_producto(p):
    return str(
        p.get("familia")
        or p.get("categoria")
        or p.get("categoría")
        or p.get("rubro")
        or p.get("grupo")
        or "Otros"
    ).strip() or "Otros"

def _familia_igual(familia_producto, familia_elegida):
    return str(familia_producto or "").strip().lower() == str(familia_elegida or "").strip().lower()


def _familias_productos():
    try:
        productos = [p for p in fetch_table("productos", "id") if p.get("activo")]
    except Exception:
        productos = []
    familias = sorted({_familia_producto(p) for p in productos})
    return familias or ["Sorrentinos", "Tartas", "Bombitas"]


def _leer_promos_fijas(db):
    try:
        return db.table("namnam_promos").select("*").order("id").execute().data or []
    except Exception:
        return []


def _leer_promos_familias(db):
    try:
        return db.table("namnam_promos_combinadas").select("*").order("id").execute().data or []
    except Exception:
        return []


def _leer_grupos(db, promo_id):
    try:
        return (
            db.table("namnam_promos_combinadas_grupos")
            .select("*")
            .eq("promo_id", promo_id)
            .order("orden")
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def render():
    user = current_user() or {}
    if user.get("rol") != "admin":
        st.error("Solo el administrador puede gestionar promociones.")
        return

    header("🏷️ Promociones", "Promos fijas y promos por familias")

    db = require_db()
    familias = _familias_productos()

    tab_nueva, tab_lista, tab_fijas = st.tabs([
        "➕ Nueva promo por familias",
        "📋 Promos por familias",
        "🏷️ Promos fijas anteriores",
    ])

    with tab_nueva:
        st.subheader("Crear promo por familias")
        st.caption("Ejemplo: Sorrentinos 2 + Tartas 3 + Bombitas 1 = precio único.")

        with st.form("nueva_promo_familias"):
            nombre = st.text_input("Nombre de promo", placeholder="Ej: PROMO COMBINADA ESPECIAL")
            descripcion = st.text_area("Descripción", placeholder="Ej: 2 sorrentinos + 3 tartas + 1 bombita")
            precio = st.number_input("Precio de la promo", min_value=0.0, step=500.0, value=0.0)
            activo = st.toggle("Activa", value=True)

            cantidad_categorias = st.number_input("Elegir cantidad de categorías/familias", min_value=1, max_value=12, step=1, value=2)

            grupos = []
            for i in range(int(cantidad_categorias)):
                with st.container(border=True):
                    st.markdown(f"#### Categoría {i + 1}")
                    c1, c2, c3 = st.columns([2, 1, 1])
                    familia = c1.selectbox("Familia", familias, key=f"promo_new_fam_{i}")
                    cantidad = c2.number_input("Cantidad", min_value=1.0, step=1.0, value=2.0, key=f"promo_new_cant_{i}")
                    excluir = c3.text_input("Excluir texto", value="premium" if "tarta" in familia.lower() else "", key=f"promo_new_exc_{i}")

                    grupos.append({
                        "familia": familia,
                        "cantidad_requerida": cantidad,
                        "texto_excluir": excluir.strip().lower(),
                        "orden": i + 1,
                    })

            guardar = st.form_submit_button("Guardar promo")

            if guardar:
                if not nombre.strip():
                    st.warning("Falta el nombre de la promo.")
                elif precio <= 0:
                    st.warning("Falta el precio de la promo.")
                else:
                    promo = db.table("namnam_promos_combinadas").insert({
                        "nombre": nombre.strip(),
                        "descripcion": descripcion.strip(),
                        "precio": precio,
                        "activo": activo,
                    }).execute().data[0]

                    for g in grupos:
                        g["promo_id"] = promo["id"]

                    db.table("namnam_promos_combinadas_grupos").insert(grupos).execute()
                    st.success("Promo guardada.")
                    st.rerun()

    with tab_lista:
        st.subheader("Promos por familias cargadas")
        promos = _leer_promos_familias(db)

        if not promos:
            st.info("Todavía no hay promos por familias.")
            return

        for promo in promos:
            grupos = _leer_grupos(db, promo["id"])
            with st.container(border=True):
                st.markdown(f"### {promo.get('nombre')}")
                st.write(f"**Precio:** {money(promo.get('precio'))}")
                if promo.get("descripcion"):
                    st.caption(promo.get("descripcion"))

                st.markdown("**Familias:**")
                for g in grupos:
                    exc = f" — excluye: {g.get('texto_excluir')}" if g.get("texto_excluir") else ""
                    st.write(f"- {g.get('familia')}: {g.get('cantidad_requerida'):g}{exc}")

                activo = st.toggle("Activa", value=bool(promo.get("activo", True)), key=f"promo_fam_act_{promo['id']}")

                with st.expander("Editar"):
                    nombre = st.text_input("Nombre", value=promo.get("nombre") or "", key=f"promo_fam_nom_{promo['id']}")
                    descripcion = st.text_area("Descripción", value=promo.get("descripcion") or "", key=f"promo_fam_desc_{promo['id']}")
                    precio = st.number_input("Precio", min_value=0.0, step=500.0, value=_float(promo.get("precio")), key=f"promo_fam_precio_{promo['id']}")

                    if st.button("Guardar datos generales", key=f"promo_fam_save_{promo['id']}"):
                        db.table("namnam_promos_combinadas").update({
                            "nombre": nombre.strip(),
                            "descripcion": descripcion.strip(),
                            "precio": precio,
                            "activo": activo,
                        }).eq("id", promo["id"]).execute()
                        st.success("Promo actualizada.")
                        st.rerun()

                    st.divider()
                    st.markdown("#### Editar familias")
                    for g in grupos:
                        with st.container(border=True):
                            familia_actual = g.get("familia") or familias[0]
                            idx = familias.index(familia_actual) if familia_actual in familias else 0
                            c1, c2, c3 = st.columns([2, 1, 1])
                            familia = c1.selectbox("Familia", familias, index=idx, key=f"promo_g_fam_{g['id']}")
                            cantidad = c2.number_input("Cantidad", min_value=1.0, step=1.0, value=_float(g.get("cantidad_requerida") or 1), key=f"promo_g_cant_{g['id']}")
                            excluir = c3.text_input("Excluir", value=g.get("texto_excluir") or "", key=f"promo_g_exc_{g['id']}")

                            c4, c5 = st.columns(2)
                            if c4.button("Guardar familia", key=f"promo_g_save_{g['id']}"):
                                db.table("namnam_promos_combinadas_grupos").update({
                                    "familia": familia,
                                    "cantidad_requerida": cantidad,
                                    "texto_excluir": excluir.strip().lower(),
                                }).eq("id", g["id"]).execute()
                                st.rerun()

                            if c5.button("Eliminar familia", key=f"promo_g_del_{g['id']}"):
                                db.table("namnam_promos_combinadas_grupos").delete().eq("id", g["id"]).execute()
                                st.rerun()

                    st.divider()
                    st.markdown("#### Agregar familia")
                    c1, c2, c3 = st.columns([2, 1, 1])
                    nueva_familia = c1.selectbox("Nueva familia", familias, key=f"promo_new_group_fam_{promo['id']}")
                    nueva_cantidad = c2.number_input("Cantidad", min_value=1.0, step=1.0, value=1.0, key=f"promo_new_group_cant_{promo['id']}")
                    nuevo_excluir = c3.text_input("Excluir", key=f"promo_new_group_exc_{promo['id']}")

                    if st.button("Agregar familia", key=f"promo_add_group_{promo['id']}"):
                        orden = max([int(g.get("orden") or 0) for g in grupos] or [0]) + 1
                        db.table("namnam_promos_combinadas_grupos").insert({
                            "promo_id": promo["id"],
                            "familia": nueva_familia,
                            "cantidad_requerida": nueva_cantidad,
                            "texto_excluir": nuevo_excluir.strip().lower(),
                            "orden": orden,
                        }).execute()
                        st.rerun()

                if st.button("Eliminar promo", key=f"promo_fam_delete_{promo['id']}"):
                    db.table("namnam_promos_combinadas").delete().eq("id", promo["id"]).execute()
                    st.success("Promo eliminada.")
                    st.rerun()

    with tab_fijas:
        st.subheader("Promos fijas anteriores")
        st.info("No se borran. Siguen disponibles para venta como promos fijas.")
        promos = _leer_promos_fijas(db)
        if promos:
            st.dataframe(pd.DataFrame(promos), use_container_width=True, hide_index=True)
        else:
            st.caption("No hay promos fijas cargadas.")
