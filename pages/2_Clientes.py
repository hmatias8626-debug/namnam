import streamlit as st
from services.auth import require_login, logout_button
from services.db import require_db, fetch_table, table
from services.ui import apply_theme, header

apply_theme(); require_login(); logout_button(); header("👥 Clientes", "Empiezan de cero")
db = require_db()

with st.form("nuevo_cliente", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input("Nombre")
    telefono = c2.text_input("Teléfono")
    direccion = c3.text_input("Dirección")
    obs = st.text_area("Observaciones")
    if st.form_submit_button("Guardar cliente"):
        if not nombre.strip(): st.warning("Falta el nombre.")
        else:
            db.table(table("clientes")).insert({"nombre": nombre.strip(), "telefono": telefono, "direccion": direccion, "observaciones": obs, "activo": True}).execute()
            st.success("Cliente guardado."); st.rerun()

clientes = fetch_table("clientes")
if not clientes: st.info("Todavía no hay clientes.")
for c in clientes:
    with st.container(border=True):
        a,b,c1,d,e = st.columns([2,2,3,3,1])
        nombre = a.text_input("Nombre", c.get("nombre") or "", key=f"n{c['id']}")
        tel = b.text_input("Teléfono", c.get("telefono") or "", key=f"t{c['id']}")
        dire = c1.text_input("Dirección", c.get("direccion") or "", key=f"d{c['id']}")
        obs = d.text_input("Obs.", c.get("observaciones") or "", key=f"o{c['id']}")
        activo = e.toggle("Activo", value=bool(c.get("activo", True)), key=f"a{c['id']}")
        if st.button("Guardar", key=f"g{c['id']}"):
            db.table(table("clientes")).update({"nombre": nombre, "telefono": tel, "direccion": dire, "observaciones": obs, "activo": activo}).eq("id", c["id"]).execute()
            st.success("Actualizado."); st.rerun()
