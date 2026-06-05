import pandas as pd
import streamlit as st
from services.db import require_db, fetch_table, money, table
from services.ui import header, card_metric

def _float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0

def _nombre_cliente(c):
    completo = f"{c.get('nombre') or ''} {c.get('apellido') or ''}".strip()
    tel = c.get("telefono") or ""
    return f"{completo} - {tel}" if tel else (completo or f"Cliente #{c.get('id')}")

def render():
    header("💰 Caja", "Ingresos, egresos, cobros y pagos de mayoristas")
    db = require_db()

    tab1, tab2 = st.tabs(["Movimiento manual", "Pago de mayorista"])

    with tab1:
        with st.form("mov_caja", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            tipo = c1.selectbox("Tipo", ["Ingreso", "Egreso"])
            importe = c2.number_input("Importe", min_value=0.0, step=100.0)
            forma_pago = c3.selectbox("Forma / medio", ["Efectivo", "Transferencia", "Mercado Pago", "Otro"])
            concepto = st.text_input("Concepto")
            obs = st.text_area("Observaciones")
            if st.form_submit_button("Registrar movimiento"):
                if not concepto.strip():
                    st.warning("Falta el concepto.")
                elif importe <= 0:
                    st.warning("El importe debe ser mayor a cero.")
                else:
                    db.table(table("caja")).insert({
                        "tipo": tipo,
                        "concepto": concepto.strip(),
                        "importe": importe,
                        "observaciones": obs.strip(),
                        "forma_pago": forma_pago,
                        "medio": forma_pago,
                    }).execute()
                    st.success("Movimiento registrado.")
                    st.rerun()

    with tab2:
        mayoristas = [c for c in fetch_table("clientes") if c.get("activo") and c.get("tipo_cliente") == "Mayorista"]
        if not mayoristas:
            st.info("No hay clientes mayoristas cargados.")
        else:
            opciones = {_nombre_cliente(c): c for c in mayoristas}
            cliente_txt = st.selectbox("Cliente mayorista", list(opciones.keys()))
            cliente = opciones[cliente_txt]
            saldo = _float(cliente.get("saldo_cuenta_corriente"))
            limite = _float(cliente.get("limite_credito"))
            disponible = limite - saldo
            c1, c2, c3 = st.columns(3)
            c1.metric("Límite", money(limite))
            c2.metric("Saldo usado", money(saldo))
            c3.metric("Disponible", money(disponible))

            with st.form("pago_mayorista", clear_on_submit=True):
                p1, p2 = st.columns(2)
                importe = p1.number_input("Importe pagado", min_value=0.0, step=100.0)
                forma_pago = p2.selectbox("Forma de pago", ["Efectivo", "Transferencia", "Mercado Pago", "Otro"])
                obs = st.text_area("Observaciones")
                if st.form_submit_button("Registrar pago"):
                    if importe <= 0:
                        st.warning("El importe debe ser mayor a cero.")
                    else:
                        db.table(table("caja")).insert({
                            "tipo": "Ingreso",
                            "concepto": f"Pago cuenta corriente - {_nombre_cliente(cliente)}",
                            "importe": importe,
                            "observaciones": obs.strip(),
                            "cliente_id": cliente["id"],
                            "forma_pago": forma_pago,
                            "medio": forma_pago,
                        }).execute()
                        db.table("namnam_credito_movimientos").insert({
                            "cliente_id": cliente["id"],
                            "tipo": "Pago",
                            "importe": importe,
                            "observaciones": obs.strip() or "Pago registrado desde caja",
                        }).execute()
                        db.table(table("clientes")).update({
                            "saldo_cuenta_corriente": saldo - importe
                        }).eq("id", cliente["id"]).execute()
                        st.success("Pago registrado y cuenta corriente actualizada.")
                        st.rerun()

    movs = fetch_table("caja", "fecha")
    ingresos = sum(_float(m.get("importe")) for m in movs if m.get("tipo") == "Ingreso")
    egresos = sum(_float(m.get("importe")) for m in movs if m.get("tipo") == "Egreso")
    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        card_metric("Ingresos", money(ingresos))
    with c2:
        card_metric("Egresos", money(egresos))
    with c3:
        card_metric("Saldo", money(ingresos - egresos))

    st.subheader("Historial")
    if movs:
        st.dataframe(pd.DataFrame(movs), use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay movimientos.")
