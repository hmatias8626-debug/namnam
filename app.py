import base64
from pathlib import Path

import pandas as pd
import streamlit as st

from services.auth import login_box, is_logged_in, current_user, logout_button
from services.db import fetch_table, money
from services.ui import apply_theme, header, card_metric

from modulos.productos import render as render_productos
from modulos.clientes import render as render_clientes
from modulos.mayoristas import render as render_mayoristas
from modulos.pedidos import render as render_pedidos
from modulos.produccion import render as render_produccion
from modulos.stock import render as render_stock
from modulos.caja import render as render_caja
from modulos.colaboradores import render as render_colaboradores
from modulos.perfil import render as render_perfil

apply_theme()


def _login_background():
    img_path = Path("assets/login_fondo.jpeg")

    if not img_path.exists():
        return

    img_b64 = base64.b64encode(img_path.read_bytes()).decode("utf-8")

    st.markdown(f"""
    <style>
    [data-testid="stSidebar"] {{
        display: none !important;
    }}

    /*
    Fondo con 2 capas:
    1) La misma imagen en cover, oscura y borrosa para llenar toda la pantalla.
    2) La imagen completa en contain a la izquierda, para que se vea como el flyer original.
    */
    .stApp {{
        background-image:
            linear-gradient(rgba(0,0,0,.30), rgba(0,0,0,.45)),
            url("data:image/jpeg;base64,{img_b64}"),
            url("data:image/jpeg;base64,{img_b64}");
        background-size:
            cover,
            cover,
            contain;
        background-position:
            center,
            center,
            left center;
        background-repeat:
            no-repeat,
            no-repeat,
            no-repeat;
        background-attachment: fixed;
    }}

    .stApp::before {{
        content: "";
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,.20);
        backdrop-filter: blur(3px);
        z-index: 0;
        pointer-events: none;
    }}

    .main .block-container {{
        position: relative;
        z-index: 1;
        max-width: 500px !important;
        padding-top: 27vh !important;
        padding-bottom: 5vh !important;
        margin-left: auto !important;
        margin-right: 9vw !important;
    }}

    /* Saca el bloque negro gigante de Streamlit */
    div[data-testid="stVerticalBlock"] > div:has(input) {{
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        padding: 0 !important;
    }}

    /* Tarjeta real del login */
    div[data-testid="stVerticalBlock"] > div:has(input) form,
    div[data-testid="stForm"] {{
        background: rgba(12, 12, 12, .48) !important;
        border: 1px solid rgba(216,155,29,.78) !important;
        border-radius: 26px !important;
        padding: 24px 28px !important;
        box-shadow: 0 18px 45px rgba(0,0,0,.42) !important;
        backdrop-filter: blur(10px) !important;
    }}

    h1 {{
        font-size: 62px !important;
        text-align: center !important;
        color: #FFF7E6 !important;
        text-shadow: 0 4px 18px rgba(0,0,0,.85) !important;
        margin-bottom: 0 !important;
    }}

    h2, h3, p, label, span {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
        text-shadow: 0 2px 8px rgba(0,0,0,.85) !important;
    }}

    label {{
        font-weight: 900 !important;
    }}

    input {{
        background-color: rgba(255,247,230,.96) !important;
        color: #111111 !important;
        font-weight: 900 !important;
        border-radius: 10px !important;
    }}

    .stButton>button {{
        width: 100%;
        min-height: 48px;
        font-size: 18px;
        background-color: #D89B1D !important;
        color: #111111 !important;
        border-radius: 14px !important;
        font-weight: 950 !important;
        border: 0 !important;
    }}

    .stButton>button:hover {{
        background-color: #ffc247 !important;
        color: #111111 !important;
    }}

    #MainMenu, footer, header {{
        visibility: hidden;
    }}

    @media (max-width: 900px) {{
        .stApp {{
            background-size:
                cover,
                cover,
                cover;
            background-position:
                center,
                center,
                center;
        }}

        .main .block-container {{
            max-width: 92vw !important;
            padding-top: 36vh !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }}

        h1 {{
            font-size: 48px !important;
        }}
    }}
    </style>
    """, unsafe_allow_html=True)

# Antes del login no se muestra menú lateral ni páginas.
if not is_logged_in():
    _login_background()
    login_box()
    st.stop()

user = current_user() or {}

MENU = {
    "🏠 Inicio": "Inicio",
    "📦 Productos": "Productos",
    "👥 Clientes": "Clientes",
    "🏪 Mayoristas": "Mayoristas",
    "📝 Pedidos": "Pedidos",
    "👨‍🍳 Producción": "Producción",
    "📊 Stock": "Stock",
    "💰 Caja": "Caja",
    "🙋 Mi perfil": "Mi perfil",
}

if user.get("rol") == "admin":
    MENU["👨‍💼 Colaboradores"] = "Colaboradores"

with st.sidebar:
    st.markdown("### 🍝 Ñam Ñam")
    opcion_label = st.radio(
        "Menú",
        list(MENU.keys()),
        label_visibility="collapsed"
    )
    seccion = MENU[opcion_label]
    st.divider()
    logout_button()

if seccion == "Productos":
    render_productos()

elif seccion == "Clientes":
    render_clientes()

elif seccion == "Mayoristas":
    render_mayoristas()

elif seccion == "Pedidos":
    render_pedidos()

elif seccion == "Producción":
    render_produccion()

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

    pendientes = sum(
        1 for p in pedidos
        if p.get("estado") in ["Pendiente", "En preparación", "Listo", "En reparto"]
    )

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

    st.caption(
        "Base limpia: clientes, stock, pedidos, caja y listas empiezan desde cero. "
        "Los productos se pueden importar desde CSV o cargar a mano."
    )
