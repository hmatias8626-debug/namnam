import pandas as pd
import streamlit as st
from services.auth import require_login, logout_button
from services.db import require_db, fetch_table, money, table
from services.ui import apply_theme, header, card_metric

apply_theme(); require_login(); logout_button(); header("💰 Caja básica", "Ingresos, egresos y saldo")
db = require_db()

with st.form("mov_caja", clear_on_submit=True):
    c1,c2 = st.columns(2)
    tipo = c1.selectbox("Tipo", ["Ingreso", "Egreso"])
    importe = c2.number_input("Importe", min_value=0.0, step=100.0)
    concepto = st.text_input("Concepto")
    obs = st.text_area("Observaciones")
    if st.form_submit_button("Registrar movimiento"):
        if not concepto.strip(): st.warning("Falta el concepto.")
        elif importe <= 0: st.warning("El importe debe ser mayor a cero.")
        else:
            db.table(table("caja")).insert({"tipo": tipo, "concepto": concepto.strip(), "importe": importe, "observaciones": obs}).execute()
            st.success("Movimiento registrado."); st.rerun()

movs = fetch_table("caja", "fecha")
ingresos = sum(float(m.get("importe") or 0) for m in movs if m.get("tipo") == "Ingreso")
egresos = sum(float(m.get("importe") or 0) for m in movs if m.get("tipo") == "Egreso")

c1,c2,c3 = st.columns(3)
with c1: card_metric("Ingresos", money(ingresos))
with c2: card_metric("Egresos", money(egresos))
with c3: card_metric("Saldo", money(ingresos-egresos))

st.subheader("Historial")
if movs: st.dataframe(pd.DataFrame(movs), use_container_width=True, hide_index=True)
else: st.info("Todavía no hay movimientos.")
