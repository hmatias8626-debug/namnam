import pandas as pd
import streamlit as st

from services.auth import current_user
from services.db import require_db, fetch_table, table
from services.ui import header


def _float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _familia_producto(p):
    familia = (
        p.get("familia")
        or p.get("categoria")
        or p.get("categoría")
        or p.get("rubro")
        or p.get("grupo")
        or "Sin familia"
    )
    familia = str(familia).strip()
    return familia if familia else "Sin familia"


def _producto_nombre_produccion(producto_id, nombre, productos_por_id):
    producto = productos_por_id.get(producto_id)

    if producto:
        familia = _familia_producto(producto)
        nombre_producto = producto.get("nombre") or nombre or f"Producto #{producto_id}"
        return f"{familia} · {nombre_producto}"

    return nombre or f"Producto #{producto_id}"


def _leer_items_pedidos(db, pedidos_ids):
    if not pedidos_ids:
        return []

    return (
        db.table(table("pedido_detalles"))
        .select("*")
        .in_("pedido_id", pedidos_ids)
        .execute()
        .data
        or []
    )


def _leer_detalle_promo(db, promo_id):
    if not promo_id:
        return []

    return (
        db.table("namnam_promos_detalle")
        .select("*")
        .eq("promo_id", promo_id)
        .execute()
        .data
        or []
    )


def _resumen_produccion(db, items, productos_por_id):
    """
    Producción NO ve promos ni precios.
    Ve productos reales a fabricar, con familia + nombre.
    """
    resumen = {}

    for it in items:
        tipo = (it.get("tipo") or "producto").lower()
        cantidad_linea = _float(it.get("cantidad"))

        if cantidad_linea <= 0:
            continue

        if tipo == "promo" and it.get("promo_id"):
            promo_id = it.get("promo_id")
            detalle_promo = _leer_detalle_promo(db, promo_id)

            for d in detalle_promo:
                producto_id = d.get("producto_id")
                nombre = _producto_nombre_produccion(
                    producto_id,
                    d.get("producto_nombre"),
                    productos_por_id
                )
                cantidad = _float(d.get("cantidad")) * cantidad_linea

                key = producto_id or nombre

                if key not in resumen:
                    resumen[key] = {
                        "Producto a producir": nombre,
                        "Cantidad": 0.0,
                    }

                resumen[key]["Cantidad"] += cantidad

        else:
            producto_id = it.get("producto_id")
            nombre = _producto_nombre_produccion(
                producto_id,
                it.get("producto_nombre"),
                productos_por_id
            )
            key = producto_id or nombre

            if key not in resumen:
                resumen[key] = {
                    "Producto a producir": nombre,
                    "Cantidad": 0.0,
                }

            resumen[key]["Cantidad"] += cantidad_linea

    return list(resumen.values())


def _pedidos_por_lote(pedidos):
    lotes = {}

    for p in pedidos:
        lote = p.get("produccion_lote") or "Sin lote"
        lotes.setdefault(lote, []).append(p)

    return lotes


def _crear_lote_id(pedidos):
    ids = "-".join(str(p.get("id")) for p in pedidos)
    return f"LOTE-{ids}"


def _cliente_pedido(p):
    return p.get("cliente_nombre") or "Sin cliente"


def render():
    user = current_user() or {}
    rol = user.get("rol")

    if rol not in ["admin", "produccion"]:
        st.error("No tenés permiso para ver Producción.")
        return

    header("👨‍🍳 Producción", "Tomar pedidos por lote y preparar productos reales")

    db = require_db()

    try:
        pedidos = fetch_table("pedidos", "fecha")
        productos = fetch_table("productos", "id")
        productos_por_id = {p.get("id"): p for p in productos}
    except Exception as e:
        st.error("No pude leer pedidos o productos.")
        st.exception(e)
        return

    pendientes = [
        p for p in pedidos
        if (p.get("estado") or "Pendiente") == "Pendiente"
    ]

    en_produccion = [
        p for p in pedidos
        if (p.get("estado") or "") == "En Producción"
    ]

    tab1, tab2 = st.tabs(["🧾 Pendientes", "👨‍🍳 En producción"])

    with tab1:
        st.subheader("Pedidos pendientes para tomar")

        if not pendientes:
            st.info("No hay pedidos pendientes.")
        else:
            seleccionados = []

            for p in reversed(pendientes):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 1, 5])

                    tomar = c1.checkbox("Tomar", key=f"tomar_pedido_{p['id']}")
                    c2.markdown(f"### #{p['id']}")
                    c3.write(f"**Cliente:** {_cliente_pedido(p)}")
                    c3.caption(f"Estado: {p.get('estado') or 'Pendiente'}")

                    if tomar:
                        seleccionados.append(p)

            if seleccionados:
                ids = [p["id"] for p in seleccionados]
                items = _leer_items_pedidos(db, ids)
                resumen = _resumen_produccion(db, items, productos_por_id)

                st.divider()
                st.subheader("Resumen del lote a tomar")
                st.write(f"Pedidos seleccionados: {', '.join('#' + str(i) for i in ids)}")

                if resumen:
                    st.dataframe(
                        pd.DataFrame(resumen),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.warning(
                        "No encontré productos reales para producir en esos pedidos. "
                        "Puede ser que algún pedido viejo haya quedado guardado sin detalle."
                    )

               if st.button("👨‍🍳 Tomar seleccionados y pasar a En Producción"):
    lote_id = _crear_lote_id(seleccionados)

    for pedido_id in ids:
        try:
            db.table(table("pedidos")).update({
                "estado": "En Producción",
                "produccion_lote": lote_id,
            }).eq("id", pedido_id).execute()

        except Exception as e:
            st.error(f"Error actualizando pedido #{pedido_id}")
            st.exception(e)
            st.stop()

    st.success(f"Lote tomado: {lote_id}")
    st.rerun()
    
    with tab2:
        st.subheader("Lotes en producción")

        if not en_produccion:
            st.info("No hay pedidos en producción.")
        else:
            lotes = _pedidos_por_lote(en_produccion)

            for lote_id, pedidos_lote in lotes.items():
                with st.container(border=True):
                    st.markdown(f"## {lote_id}")

                    pedidos_ids = [p["id"] for p in pedidos_lote]
                    st.caption(f"Pedidos: {', '.join('#' + str(i) for i in pedidos_ids)}")

                    items = _leer_items_pedidos(db, pedidos_ids)
                    resumen = _resumen_produccion(db, items, productos_por_id)

                    st.markdown("### Productos a producir")

                    if resumen:
                        st.dataframe(
                            pd.DataFrame(resumen),
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.warning("No encontré productos reales para este lote.")

                    st.markdown("### Pedidos del lote")

                    datos_pedidos = [
                        {
                            "Pedido": f"#{p.get('id')}",
                            "Cliente": _cliente_pedido(p),
                            "Estado": p.get("estado"),
                        }
                        for p in pedidos_lote
                    ]

                    st.dataframe(
                        pd.DataFrame(datos_pedidos),
                        use_container_width=True,
                        hide_index=True
                    )

                    if st.button("✅ Marcar lote como Listo", key=f"listo_{lote_id}"):
                        for pedido_id in pedidos_ids:
                            db.table(table("pedidos")).update({
                                "estado": "Listo"
                            }).eq("id", pedido_id).execute()

                        st.success(f"Lote {lote_id} marcado como listo.")
                        st.rerun()
