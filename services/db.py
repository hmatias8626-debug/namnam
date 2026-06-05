import streamlit as st
from supabase import create_client, Client

TABLES = {
    "usuarios": "namnam_usuarios",
    "productos": "namnam_productos",
    "clientes": "namnam_clientes",
    "pedidos": "namnam_pedidos",
    "pedido_detalles": "namnam_pedido_detalles",
    "stock": "namnam_stock",
    "caja": "namnam_caja",
}

@st.cache_resource
def get_supabase() -> Client | None:
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)

def require_db():
    db = get_supabase()
    if db is None:
        st.error("Faltan SUPABASE_URL y SUPABASE_KEY en los secrets de Streamlit.")
        st.stop()
    return db

def table(name: str) -> str:
    return TABLES.get(name, name)

def fetch_table(name: str, order: str = "id"):
    db = require_db()
    return db.table(table(name)).select("*").order(order).execute().data

def money(value):
    try:
        return f"$ {float(value):,.0f}".replace(",", ".")
    except Exception:
        return "$ 0"
