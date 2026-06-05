import pandas as pd
import streamlit as st

from services.auth import login_box, is_logged_in, current_user, logout_button
from services.db import fetch_table, money
from services.ui import apply_theme, header, card_metric

from modulos.productos import render as render_productos
from modulos.clientes import render as render_clientes
from modulos.pedidos import render as render_pedidos
from modulos.stock import render as render_stock
from modulos.caja import render as render_caja
from modulos.colaboradores import render as render_colaboradores
from modulos.perfil import render as render_perfil

apply_theme()

# Antes del login no se muestra menú lateral ni páginas.
if not is_logged_in():
    login_box()
    st.stop()

user = current_user() or {}

with st.sidebar:
    st.markdown("### Ñam Ñam")
    opciones = ["Inicio", "Productos", "Clientes", "Pedidos", "Stock", "Caja", "Mi perfil"]
    if user.get("rol") == "admin":
        opciones.append("Colaboradores")
    seccion = st.radio("Menú", opciones, label_visibility="collapsed")
    st.divider()
    logout_button()

if seccion == "Productos":
    render_productos()
elif seccion == "Clientes":
    render_clientes()
elif seccion == "Pedidos":
    render_pedidos()
elif seccion == "Stock":
    render_stock()
elif seccion == "Caja":
    render_caja()
elif seccion == "Mi perfil":
    render_perfil()
elif seccion == "Colaboradores":
    render_colaboradores()
else:
    header("🍝 Ñam Ñam Web", "Fase 1: productos, clientes, pedidos, stock simple, caja básica y login")

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
    with c1:
        card_metric("Productos activos", str(sum(1 for p in productos if p.get("activo"))))
    with c2:
        card_metric("Clientes activos", str(sum(1 for c in clientes if c.get("activo"))))
    with c3:
        card_metric("Pedidos abiertos", str(pendientes))
    with c4:
        card_metric("Saldo caja", money(ingresos - egresos))

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
