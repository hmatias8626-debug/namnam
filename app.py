import pandas as pd
import streamlit as st
from services.auth import require_login, logout_button
from services.db import require_db, fetch_table, money
from services.ui import apply_theme, header, card_metric

apply_theme()
require_login()
logout_button()
header("🍝 Ñam Ñam Web", "Fase 1: productos, clientes, pedidos, stock simple, caja básica y login")

db = require_db()

try:
    productos = fetch_table("productos")
    clientes = fetch_table("clientes")
    pedidos = fetch_table("pedidos", "fecha")
    caja = fetch_table("caja", "fecha")
except Exception as e:
    st.error("No pude leer Supabase. Revisá que las tablas namnam_ existan y que hayas configurado los secrets.")
    st.exception(e)
    st.stop()

pendientes = sum(1 for p in pedidos if p.get("estado") in ["Pendiente", "En preparación", "Listo", "En reparto"])
ingresos = sum(float(m.get("importe") or 0) for m in caja if m.get("tipo") == "Ingreso")
egresos = sum(float(m.get("importe") or 0) for m in caja if m.get("tipo") == "Egreso")

c1, c2, c3, c4 = st.columns(4)
with c1: card_metric("Productos activos", str(sum(1 for p in productos if p.get("activo"))))
with c2: card_metric("Clientes activos", str(sum(1 for c in clientes if c.get("activo"))))
with c3: card_metric("Pedidos abiertos", str(pendientes))
with c4: card_metric("Saldo caja", money(ingresos - egresos))

st.divider()
col_a, col_b = st.columns([1, 1])
with col_a:
    st.subheader("📌 Últimos pedidos")
    if pedidos:
        df = pd.DataFrame(pedidos).tail(8)
        cols = [c for c in ["id", "cliente_nombre", "estado", "total", "fecha"] if c in df.columns]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay pedidos.")
with col_b:
    st.subheader("💰 Últimos movimientos de caja")
    if caja:
        df = pd.DataFrame(caja).tail(8)
        cols = [c for c in ["tipo", "concepto", "importe", "fecha"] if c in df.columns]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay movimientos de caja.")

st.caption("Base limpia: clientes, stock, pedidos, caja y listas empiezan desde cero. Los productos se pueden importar desde CSV o cargar a mano.")
