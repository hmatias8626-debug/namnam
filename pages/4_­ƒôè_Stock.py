import pandas as pd
import streamlit as st
from services.auth import require_login, logout_button
from services.db import require_db, fetch_table, table
from services.ui import apply_theme, header

apply_theme(); require_login(); logout_button(); header("📊 Stock simple", "Arranca en cero. Ajustes manuales por producto.")
db = require_db()
productos = [p for p in fetch_table("productos") if p.get("activo")]

with st.form("mov_stock", clear_on_submit=True):
    prod_map = {f"{p['nombre']} ({p.get('unidad') or 'unidad'})": p for p in productos}
    producto_txt = st.selectbox("Producto", list(prod_map.keys()) if prod_map else [])
    cantidad = st.number_input("Cantidad actual / ajuste", step=1.0)
    if st.form_submit_button("Guardar stock"):
        if not producto_txt: st.warning("Primero cargá productos.")
        else:
            p = prod_map[producto_txt]
            existente = db.table(table("stock")).select("id").eq("producto_id", p["id"]).execute().data
            data = {"producto_id": p["id"], "cantidad": cantidad}
            if existente:
                db.table(table("stock")).update(data).eq("id", existente[0]["id"]).execute()
            else:
                db.table(table("stock")).insert(data).execute()
            st.success("Stock actualizado."); st.rerun()

st.subheader("Stock actual")
stock = fetch_table("stock")
prod_by_id = {p["id"]: p for p in productos}
rows = []
for s in stock:
    p = prod_by_id.get(s.get("producto_id"), {})
    rows.append({"producto": p.get("nombre", s.get("producto_id")), "categoria": p.get("categoria", ""), "cantidad": s.get("cantidad", 0), "unidad": p.get("unidad", "")})
if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else: st.info("Todavía no hay stock cargado.")
