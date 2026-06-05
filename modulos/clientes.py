import pandas as pd
import streamlit as st
from services.db import require_db, fetch_table, money, table
from services.ui import header

TIPOS_CLIENTE = ["Minorista", "Mayorista"]

def _float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0

def _nombre_completo(c):
    return f"{c.get('nombre') or ''} {c.get('apellido') or ''}".strip() or f"Cliente #{c.get('id')}"

def render():
    header("👥 Clientes", "Minoristas, mayoristas y cuenta corriente")
    db = require_db()

    with st.expander("➕ Alta de cliente", expanded=True):
        with st.form("nuevo_cliente", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre")
            apellido = c2.text_input("Apellido")
            c3, c4 = st.columns(2)
            telefono = c3.text_input("Teléfono")
            direccion = c4.text_input("Dirección / Domicilio")
            c5, c6 = st.columns(2)
            tipo_cliente = c5.selectbox("Tipo de cliente", TIPOS_CLIENTE)
            limite_credito = 0.0
            if tipo_cliente == "Mayorista":
                limite_credito = c6.number_input("Límite de crédito", min_value=0.0, step=1000.0)
            else:
                c6.info("Minorista / consumidor final")
            obs = st.text_area("Observaciones")

            if st.form_submit_button("Guardar cliente"):
                if not nombre.strip():
                    st.warning("Falta el nombre.")
                else:
                    db.table(table("clientes")).insert({
                        "nombre": nombre.strip(),
                        "apellido": apellido.strip(),
                        "telefono": telefono.strip(),
                        "direccion": direccion.strip(),
                        "tipo_cliente": tipo_cliente,
                        "limite_credito": limite_credito,
                        "saldo_cuenta_corriente": 0,
                        "observaciones": obs.strip(),
                        "activo": True,
                    }).execute()
                    st.success("Cliente guardado.")
                    st.rerun()

    clientes = fetch_table("clientes")
    st.subheader("Listado de clientes")
    if not clientes:
        st.info("Todavía no hay clientes.")
        return

    for c in clientes:
        with st.container(border=True):
            st.markdown(f"### {_nombre_completo(c)}")
            a, b, c1 = st.columns([2, 2, 2])
            nombre = a.text_input("Nombre", c.get("nombre") or "", key=f"n{c['id']}")
            apellido = b.text_input("Apellido", c.get("apellido") or "", key=f"ap{c['id']}")
            telefono = c1.text_input("Teléfono", c.get("telefono") or "", key=f"t{c['id']}")
            d, e = st.columns([3, 3])
            direccion = d.text_input("Dirección", c.get("direccion") or "", key=f"d{c['id']}")
            obs = e.text_input("Obs.", c.get("observaciones") or "", key=f"o{c['id']}")
            f, g, h = st.columns([2, 2, 1])
            tipo_actual = c.get("tipo_cliente") or "Minorista"
            idx = TIPOS_CLIENTE.index(tipo_actual) if tipo_actual in TIPOS_CLIENTE else 0
            tipo_edit = f.selectbox("Tipo", TIPOS_CLIENTE, index=idx, key=f"tipo{c['id']}")
            limite_edit = g.number_input("Límite crédito", min_value=0.0, step=1000.0, value=_float(c.get("limite_credito")), key=f"lim{c['id']}")
            activo = h.toggle("Activo", value=bool(c.get("activo", True)), key=f"a{c['id']}")

            saldo = _float(c.get("saldo_cuenta_corriente"))
            disponible = limite_edit - saldo
            if tipo_edit == "Mayorista":
                x1, x2, x3 = st.columns(3)
                x1.metric("Límite", money(limite_edit))
                x2.metric("Saldo usado", money(saldo))
                if disponible < 0:
                    x3.error(f"Disponible: {money(disponible)}")
                else:
                    x3.success(f"Disponible: {money(disponible)}")

            if st.button("Guardar", key=f"g{c['id']}"):
                db.table(table("clientes")).update({
                    "nombre": nombre.strip(),
                    "apellido": apellido.strip(),
                    "telefono": telefono.strip(),
                    "direccion": direccion.strip(),
                    "tipo_cliente": tipo_edit,
                    "limite_credito": limite_edit,
                    "observaciones": obs.strip(),
                    "activo": activo,
                }).eq("id", c["id"]).execute()
                st.success("Cliente actualizado.")
                st.rerun()
