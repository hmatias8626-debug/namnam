import pandas as pd
import streamlit as st

from services.auth import current_user
from services.db import require_db, fetch_table, table, money
from services.ui import header


def _float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _producto_label(p):
    nombre = p.get("nombre") or f"Producto #{p.get('id')}"
    familia = p.get("familia") or p.get("categoria") or p.get("rubro") or "Sin familia"
    return f"{familia} · {nombre}"


def render():
    user = current_user() or {}
    rol = user.get("rol")

    if rol not in ["admin"]:
        st.error("Solo el administrador puede gestionar promociones.")
        return

    header("🏷️ Promociones", "Combos y promos con precio independiente")

    db = require_db()

    productos = [p for p in fetch_table("productos") if p.get("activo")]
    promos = fetch_table("promos")

    tab1, tab2 = st.tabs(["➕ Nueva promo", "🏷️ Promos cargadas"])

    with tab1:
        st.subheader("Crear promoción")

        if not productos:
            st.warning("Primero cargá productos.")
        else:
            with st.form("crear_promo"):
                nombre = st.text_input("Nombre de la promo", placeholder="Ej: Combo semanal")
                descripcion = st.text_area("Descripción", placeholder="Ej: 2 docenas + 3 tartas + 12 bombas")
                precio = st.number_input("Precio promo", min_value=0.0, step=500.0)
                activo = st.toggle("Activa", value=True)

                st.markdown("### Productos incluidos")

                producto_opciones = {_producto_label(p): p for p in productos}
                seleccionados = st.multiselect(
                    "Elegí los productos que incluye la promo",
                    list(producto_opciones.keys())
                )

                cantidades = {}

                for label in seleccionados:
                    p = producto_opciones[label]
                    cantidades[p["id"]] = st.number_input(
                        f"Cantidad: {label}",
                        min_value=0.0,
                        step=1.0,
                        key=f"cant_promo_new_{p['id']}"
                    )

                guardar = st.form_submit_button("Guardar promo")

                if guardar:
                    if not nombre.strip():
                        st.warning("Falta el nombre de la promo.")
                    elif precio <= 0:
                        st.warning("El precio debe ser mayor a 0.")
                    elif not seleccionados:
                        st.warning("Elegí al menos un producto.")
                    else:
                        promo = db.table(table("promos")).insert({
                            "nombre": nombre.strip(),
                            "descripcion": descripcion.strip(),
                            "precio": precio,
                            "activo": activo,
                        }).execute().data[0]

                        detalles = []

                        for label in seleccionados:
                            p = producto_opciones[label]
                            cant = _float(cantidades.get(p["id"]))

                            if cant > 0:
                                detalles.append({
                                    "promo_id": promo["id"],
                                    "producto_id": p["id"],
                                    "producto_nombre": p.get("nombre"),
                                    "cantidad": cant,
                                })

                        if detalles:
                            db.table(table("promos_detalle")).insert(detalles).execute()

                        st.success("Promo creada.")
                        st.rerun()

    with tab2:
        st.subheader("Promociones cargadas")

        if not promos:
            st.info("Todavía no hay promociones cargadas.")
            return

        for promo in reversed(promos):
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])

                c1.markdown(f"### 🏷️ {promo.get('nombre')}")
                c1.caption(promo.get("descripcion") or "")

                c2.markdown("Precio")
                c2.markdown(f"## {money(promo.get('precio'))}")

                activo = c3.toggle(
                    "Activa",
                    value=bool(promo.get("activo", True)),
                    key=f"promo_activa_{promo['id']}"
                )

                if activo != bool(promo.get("activo", True)):
                    db.table(table("promos")).update({"activo": activo}).eq("id", promo["id"]).execute()
                    st.rerun()

                detalles = (
                    db.table(table("promos_detalle"))
                    .select("*")
                    .eq("promo_id", promo["id"])
                    .execute()
                    .data
                    or []
                )

                if detalles:
                    st.markdown("**Incluye:**")
                    st.dataframe(
                        pd.DataFrame([
                            {
                                "Producto": d.get("producto_nombre"),
                                "Cantidad": d.get("cantidad"),
                            }
                            for d in detalles
                        ]),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.warning("Esta promo no tiene productos asociados.")

                with st.expander("Editar datos principales"):
                    nuevo_nombre = st.text_input(
                        "Nombre",
                        promo.get("nombre") or "",
                        key=f"promo_nombre_{promo['id']}"
                    )
                    nueva_descripcion = st.text_area(
                        "Descripción",
                        promo.get("descripcion") or "",
                        key=f"promo_desc_{promo['id']}"
                    )
                    nuevo_precio = st.number_input(
                        "Precio",
                        min_value=0.0,
                        step=500.0,
                        value=_float(promo.get("precio")),
                        key=f"promo_precio_{promo['id']}"
                    )

                    col_g, col_b = st.columns([1, 1])

                    if col_g.button("Guardar cambios", key=f"guardar_promo_{promo['id']}"):
                        db.table(table("promos")).update({
                            "nombre": nuevo_nombre.strip(),
                            "descripcion": nueva_descripcion.strip(),
                            "precio": nuevo_precio,
                            "activo": activo,
                        }).eq("id", promo["id"]).execute()

                        st.success("Promo actualizada.")
                        st.rerun()

                    if col_b.button("Eliminar promo", key=f"borrar_promo_{promo['id']}"):
                        db.table(table("promos_detalle")).delete().eq("promo_id", promo["id"]).execute()
                        db.table(table("promos")).delete().eq("id", promo["id"]).execute()
                        st.success("Promo eliminada.")
                        st.rerun()