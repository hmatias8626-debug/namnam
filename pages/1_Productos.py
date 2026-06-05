import pandas as pd
import streamlit as st
from services.auth import require_login, logout_button
from services.db import require_db, fetch_table, money, table
from services.ui import apply_theme, header

apply_theme(); require_login(); logout_button(); header("📦 Productos", "Alta, modificación y baja lógica")
db = require_db()

with st.expander("➕ Nuevo producto", expanded=True):
    with st.form("nuevo_producto", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        nombre = c1.text_input("Nombre")
        categoria = c2.text_input("Categoría", value="Pastas")
        unidad = c3.text_input("Unidad", value="unidad")
        precio = c4.number_input("Precio venta", min_value=0.0, step=100.0)
        if st.form_submit_button("Guardar producto"):
            if not nombre.strip():
                st.warning("Falta el nombre.")
            else:
                db.table(table("productos")).insert({"nombre": nombre.strip(), "categoria": categoria.strip(), "unidad": unidad.strip(), "precio_venta": precio, "activo": True}).execute()
                st.success("Producto guardado."); st.rerun()

with st.expander("📥 Importar productos desde CSV"):
    st.caption("Usá columnas: nombre, categoria, unidad, precio_venta, activo")
    file = st.file_uploader("CSV de productos", type=["csv"])
    if file and st.button("Importar CSV"):
        df = pd.read_csv(file)
        rows = df.to_dict(orient="records")
        db.table(table("productos")).insert(rows).execute()
        st.success(f"Importados {len(rows)} productos."); st.rerun()

productos = fetch_table("productos")
st.subheader("Listado")
if not productos:
    st.info("No hay productos cargados.")
else:
    for p in productos:
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([3,2,1,1,1])
            nombre = c1.text_input("Nombre", p.get("nombre") or "", key=f"n{p['id']}")
            categoria = c2.text_input("Categoría", p.get("categoria") or "", key=f"c{p['id']}")
            unidad = c3.text_input("Unidad", p.get("unidad") or "unidad", key=f"u{p['id']}")
            precio = c4.number_input("Precio", value=float(p.get("precio_venta") or 0), step=100.0, key=f"pr{p['id']}")
            activo = c5.toggle("Activo", value=bool(p.get("activo", True)), key=f"a{p['id']}")
            b1, b2 = st.columns([1,5])
            if b1.button("Guardar", key=f"g{p['id']}"):
                db.table(table("productos")).update({"nombre": nombre, "categoria": categoria, "unidad": unidad, "precio_venta": precio, "activo": activo}).eq("id", p["id"]).execute()
                st.success("Actualizado."); st.rerun()
            b2.caption(f"Precio actual: {money(p.get('precio_venta'))}")
