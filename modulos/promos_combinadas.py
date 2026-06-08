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
        return ["Sorrentinos", "Tartas", "Bombitas de papa"]
    familias = sorted({
        str(p.get("familia") or p.get("categoria") or p.get("categoría") or p.get("rubro") or p.get("grupo") or "Otros").strip()
        for p in productos
        if str(p.get("familia") or p.get("categoria") or p.get("categoría") or p.get("rubro") or p.get("grupo") or "Otros").strip()
    })
    return familias or ["Sorrentinos", "Tartas", "Bombitas de papa"]


def _leer_promos(db):
    try:
        return db.table("namnam_promos_combinadas").select("*").order("id").execute().data or []
    except Exception:
        return []


def _leer_grupos(db, promo_id):
    try:
        return db.table("namnam_promos_combinadas_grupos").select("*").eq("promo_id", promo_id).order("orden").execute().data or []
    except Exception:
        return []


def render():
    user = current_user() or {}
    if user.get("rol") != "admin":
        st.error("Solo el administrador puede gestionar promos combinadas.")
        return

    header("🧩 Promos combinadas", "Promos con varias familias y cantidades específicas")
    db = require_db()
    familias = _familias_productos()
    tab_nueva, tab_lista = st.tabs(["➕ Nueva promo combinada", "📋 Promos cargadas"])

    with tab_nueva:
        with st.form("nueva_promo_combinada"):
            nombre = st.text_input("Nombre", value="PROMO SEMANAL")
            descripcion = st.text_area("Descripción", value="2 sorrentinos + 2 tartas + 12 bombitas de papa")
            precio = st.number_input("Precio total de la promo", min_value=0.0, step=500.0, value=50000.0)
            activo = st.toggle("Activa", value=True)
            st.markdown("### Grupos de la promo")
            cantidad_grupos = st.number_input("Cantidad de grupos", min_value=1, max_value=8, value=3, step=1)
            grupos = []
            for i in range(int(cantidad_grupos)):
                with st.container(border=True):
                    st.markdown(f"#### Grupo {i + 1}")
                    c1, c2, c3 = st.columns([2, 1, 1])
                    familia = c1.selectbox("Familia", familias, key=f"nuevo_combo_familia_{i}")
                    cantidad = c2.number_input("Cantidad", min_value=1.0, step=1.0, value=2.0, key=f"nuevo_combo_cant_{i}")
                    excluir = c3.text_input("Excluir texto", value="premium" if "tarta" in familia.lower() else "", key=f"nuevo_combo_excluir_{i}")
                    grupos.append({"familia": familia, "cantidad_requerida": cantidad, "texto_excluir": excluir.strip().lower(), "orden": i + 1})
            if st.form_submit_button("Guardar promo combinada"):
                if not nombre.strip():
                    st.warning("Falta el nombre.")
                else:
                    promo = db.table("namnam_promos_combinadas").insert({"nombre": nombre.strip(), "descripcion": descripcion.strip(), "precio": precio, "activo": activo}).execute().data[0]
                    for g in grupos:
                        g["promo_id"] = promo["id"]
                    db.table("namnam_promos_combinadas_grupos").insert(grupos).execute()
                    st.success("Promo combinada guardada.")
                    st.rerun()

    with tab_lista:
        promos = _leer_promos(db)
        if not promos:
            st.info("Todavía no hay promos combinadas.")
            return
        for promo in promos:
            grupos = _leer_grupos(db, promo["id"])
            with st.container(border=True):
                st.markdown(f"### {promo.get('nombre')}")
                st.write(f"**Precio:** {money(promo.get('precio'))}")
                if promo.get("descripcion"):
                    st.caption(promo.get("descripcion"))
                activo = st.toggle("Activa", value=bool(promo.get("activo", True)), key=f"combo_activo_{promo['id']}")
                st.markdown("**Grupos:**")
                for g in grupos:
                    extra = f" — excluye: {g.get('texto_excluir')}" if g.get("texto_excluir") else ""
                    st.write(f"- {g.get('cantidad_requerida'):g} x {g.get('familia')}{extra}")
                with st.expander("Editar promo"):
                    nombre = st.text_input("Nombre", value=promo.get("nombre") or "", key=f"combo_nom_{promo['id']}")
                    descripcion = st.text_area("Descripción", value=promo.get("descripcion") or "", key=f"combo_desc_{promo['id']}")
                    precio = st.number_input("Precio", min_value=0.0, step=500.0, value=_float(promo.get("precio")), key=f"combo_precio_{promo['id']}")
                    if st.button("Guardar datos generales", key=f"combo_guardar_{promo['id']}"):
                        db.table("namnam_promos_combinadas").update({"nombre": nombre.strip(), "descripcion": descripcion.strip(), "precio": precio, "activo": activo}).eq("id", promo["id"]).execute()
                        st.success("Promo actualizada.")
                        st.rerun()
                    st.divider()
                    st.markdown("#### Editar grupos")
                    for g in grupos:
                        with st.container(border=True):
                            st.write(f"Grupo {g.get('orden')}")
                            familia_actual = g.get("familia") or familias[0]
                            idx = familias.index(familia_actual) if familia_actual in familias else 0
                            c1, c2, c3 = st.columns([2, 1, 1])
                            familia = c1.selectbox("Familia", familias, index=idx, key=f"combo_g_fam_{g['id']}")
                            cantidad = c2.number_input("Cantidad", min_value=1.0, step=1.0, value=_float(g.get("cantidad_requerida") or 1), key=f"combo_g_cant_{g['id']}")
                            excluir = c3.text_input("Excluir", value=g.get("texto_excluir") or "", key=f"combo_g_exc_{g['id']}")
                            c4, c5 = st.columns(2)
                            if c4.button("Guardar grupo", key=f"combo_g_save_{g['id']}"):
                                db.table("namnam_promos_combinadas_grupos").update({"familia": familia, "cantidad_requerida": cantidad, "texto_excluir": excluir.strip().lower()}).eq("id", g["id"]).execute()
                                st.rerun()
                            if c5.button("Eliminar grupo", key=f"combo_g_del_{g['id']}"):
                                db.table("namnam_promos_combinadas_grupos").delete().eq("id", g["id"]).execute()
                                st.rerun()
                    st.divider()
                    st.markdown("#### Agregar grupo")
                    c1, c2, c3 = st.columns([2, 1, 1])
                    nueva_familia = c1.selectbox("Nueva familia", familias, key=f"combo_new_fam_{promo['id']}")
                    nueva_cantidad = c2.number_input("Nueva cantidad", min_value=1.0, step=1.0, value=1.0, key=f"combo_new_cant_{promo['id']}")
                    nuevo_excluir = c3.text_input("Nuevo excluir", key=f"combo_new_exc_{promo['id']}")
                    if st.button("Agregar grupo", key=f"combo_add_group_{promo['id']}"):
                        orden = max([int(g.get("orden") or 0) for g in grupos] or [0]) + 1
                        db.table("namnam_promos_combinadas_grupos").insert({"promo_id": promo["id"], "familia": nueva_familia, "cantidad_requerida": nueva_cantidad, "texto_excluir": nuevo_excluir.strip().lower(), "orden": orden}).execute()
                        st.rerun()
                if st.button("Eliminar promo completa", key=f"combo_delete_{promo['id']}"):
                    db.table("namnam_promos_combinadas").delete().eq("id", promo["id"]).execute()
                    st.success("Promo eliminada.")
                    st.rerun()
