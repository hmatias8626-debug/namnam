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


def _crear_lote_id(pedidos):
    ids = "-".join(str(p.get("id")) for p in pedidos)
    return f"LOTE-{ids}"


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


def _resumen_items(items):
    resumen = {}

    for it in items:
        producto_id = it.get("producto_id")
        nombre = it.get("producto_nombre") or f"Producto #{producto_id}"
        cantidad = _float(it.get("cantidad"))
        subtotal = _float(it.get("subtotal"))

        key = producto_id or nombre

        if key not in resumen:
            resumen[key] = {
                "Producto": nombre,
                "Cantidad": 0.0,
                "Subtotal pedidos": 0.0,
            }

        resumen[key]["Cantidad"] += cantidad
        resumen[key]["Subtotal pedidos"] += subtotal

    return list(resumen.values())


def _pedidos_por_lote(pedidos):
    lotes = {}

    for p in pedidos:
        lote = p.get("produccion_lote") or "Sin lote"
        lotes.setdefault(lote, []).append(p)

    return lotes


def render():
    user = current_user() or {}
    rol = user.get("rol")

    if rol not in ["admin", "produccion"]:
        st.error("No tenés permiso para ver Producción.")
        return

    header("👨‍🍳 Producción", "Tomar pedidos por lote y marcarlos como listos")

    db = require_db()

    try:
        pedidos = fetch_table("pedidos", "fecha")
    except Exception as e:
        st.error("No pude leer pedidos.")
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
                    c1, c2, c3, c4 = st.columns([1, 1, 3, 2])

                    tomar = c1.checkbox("Tomar", key=f"tomar_pedido_{p['id']}")
                    c2.markdown(f"### #{p['id']}")
                    c3.write(f"**Cliente:** {p.get('cliente_nombre') or 'Sin cliente'}")
                    c3.caption(f"Estado: {p.get('estado') or 'Pendiente'}")
                    c4.markdown(f"### {money(p.get('total'))}")

                    if tomar:
                        seleccionados.append(p)

            if seleccionados:
                ids = [p["id"] for p in seleccionados]
                items = _leer_items_pedidos(db, ids)
                resumen = _resumen_items(items)

                st.divider()
                st.subheader("Resumen del lote a tomar")

                st.write(f"Pedidos seleccionados: {', '.join('#' + str(i) for i in ids)}")

                if resumen:
                    st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)
                else:
                    st.warning("No encontré detalles de esos pedidos.")

                if st.button("👨‍🍳 Tomar seleccionados y pasar a En Producción"):
                    lote_id = _crear_lote_id(seleccionados)

                    for pedido_id in ids:
                        db.table(table("pedidos")).update({
                            "estado": "En Producción",
                            "produccion_lote": lote_id,
                        }).eq("id", pedido_id).execute()

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
                    resumen = _resumen_items(items)

                    if resumen:
                        st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)
                    else:
                        st.warning("No encontré detalles del lote.")

                    st.markdown("### Pedidos del lote")
                    datos_pedidos = []
                    for p in pedidos_lote:
                        datos_pedidos.append({
                            "Pedido": f"#{p.get('id')}",
                            "Cliente": p.get("cliente_nombre") or "Sin cliente",
                            "Total": money(p.get("total")),
                            "Estado": p.get("estado"),
                        })

                    st.dataframe(pd.DataFrame(datos_pedidos), use_container_width=True, hide_index=True)

                    if st.button("✅ Marcar lote como Listo", key=f"listo_{lote_id}"):
                        for pedido_id in pedidos_ids:
                            db.table(table("pedidos")).update({
                                "estado": "Listo"
                            }).eq("id", pedido_id).execute()

                        st.success(f"Lote {lote_id} marcado como listo.")
                        st.rerun()
