import pandas as pd
import streamlit as st
from services.auth import require_login, logout_button
from services.db import require_db, fetch_table, money, table
from services.ui import apply_theme, header

apply_theme(); require_login(); logout_button(); header("📝 Pedidos", "Pendiente → En preparación → Listo → En reparto → Entregado")
db = require_db()
ESTADOS = ["Pendiente", "En preparación", "Listo", "En reparto", "Entregado"]

productos = [p for p in fetch_table("productos") if p.get("activo")]
clientes = [c for c in fetch_table("clientes") if c.get("activo")]

with st.expander("➕ Crear pedido", expanded=True):
    if not productos:
        st.warning("Primero cargá productos.")
    else:
        cliente_opciones = {f"{c['nombre']} - {c.get('telefono') or ''}": c for c in clientes}
        cliente_txt = st.selectbox("Cliente guardado", ["Venta mostrador / sin cliente"] + list(cliente_opciones.keys()))
        cliente_manual = st.text_input("O nombre manual")
        obs = st.text_area("Observaciones")
        st.write("Productos del pedido")
        items = []
        for p in productos:
            c1,c2,c3 = st.columns([3,1,1])
            unidad = p.get("unidad") or "unidad"
            c1.write(f"**{p['nombre']}**  · {money(p.get('precio_venta'))} / {unidad}")
            cant = c2.number_input("Cantidad", min_value=0.0, step=1.0, key=f"cant{p['id']}")
            precio = float(p.get("precio_venta") or 0)
            if cant > 0:
                items.append({"producto_id": p["id"], "producto_nombre": p["nombre"], "cantidad": cant, "precio_unitario": precio, "subtotal": cant * precio})
            c3.write(money(cant * precio))
        total = sum(i["subtotal"] for i in items)
        st.subheader(f"Total: {money(total)}")
        if st.button("Guardar pedido"):
            cliente_id = None; cliente_nombre = cliente_manual.strip() or "Venta mostrador"
            if cliente_txt != "Venta mostrador / sin cliente":
                cli = cliente_opciones[cliente_txt]; cliente_id = cli["id"]; cliente_nombre = cli["nombre"]
            if not items: st.warning("Agregá al menos un producto.")
            else:
                pedido = db.table(table("pedidos")).insert({"cliente_id": cliente_id, "cliente_nombre": cliente_nombre, "estado":"Pendiente", "total": total, "observaciones": obs}).execute().data[0]
                for it in items: it["pedido_id"] = pedido["id"]
                db.table(table("pedido_detalles")).insert(items).execute()
                st.success("Pedido guardado."); st.rerun()

st.subheader("Pedidos")
pedidos = fetch_table("pedidos", "fecha")
if not pedidos: st.info("Todavía no hay pedidos.")
for p in reversed(pedidos):
    with st.container(border=True):
        c1,c2,c3,c4 = st.columns([1,3,2,2])
        c1.markdown(f"### #{p['id']}")
        c2.write(f"**Cliente:** {p.get('cliente_nombre') or 'Sin cliente'}")
        estado_actual = p.get("estado") if p.get("estado") in ESTADOS else "Pendiente"
        nuevo_estado = c3.selectbox("Estado", ESTADOS, index=ESTADOS.index(estado_actual), key=f"e{p['id']}")
        c4.markdown(f"### {money(p.get('total'))}")
        if st.button("Actualizar estado", key=f"up{p['id']}"):
            db.table(table("pedidos")).update({"estado": nuevo_estado}).eq("id", p["id"]).execute()
            st.success("Estado actualizado."); st.rerun()
        items = db.table(table("pedido_detalles")).select("producto_nombre,cantidad,precio_unitario,subtotal").eq("pedido_id", p["id"]).execute().data
        if items: st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)
        if p.get("observaciones"): st.caption(p["observaciones"])
