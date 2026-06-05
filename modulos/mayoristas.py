import pandas as pd
import streamlit as st

from services.db import require_db, fetch_table, table, money
from services.ui import header


def _nombre_completo(cliente: dict) -> str:
    nombre = cliente.get("nombre") or ""
    apellido = cliente.get("apellido") or ""
    completo = f"{nombre} {apellido}".strip()
    return completo or f"Cliente #{cliente.get('id')}"


def render():
    header(
        "🏪 Mayoristas",
        "Cuenta corriente, crédito disponible e historial de movimientos"
    )

    db = require_db()

    try:
        mayoristas = fetch_table("mayoristas_credito")
    except Exception:
        st.warning(
            "Todavía no existe la vista namnam_mayoristas_credito. "
            "Ejecutá primero el SQL de mayoristas/crédito en Supabase."
        )
        mayoristas = []

    if not mayoristas:
        st.info("Todavía no hay clientes mayoristas cargados.")
        st.caption("Cargalos desde Clientes seleccionando tipo Mayorista.")
        return

    total_credito = sum(float(c.get("limite_credito") or 0) for c in mayoristas)
    total_usado = sum(float(c.get("saldo_cuenta_corriente") or 0) for c in mayoristas)
    total_disponible = total_credito - total_usado
    excedidos = sum(1 for c in mayoristas if c.get("excedido"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mayoristas", len(mayoristas))
    c2.metric("Crédito total", money(total_credito))
    c3.metric("Saldo usado", money(total_usado))
    c4.metric("Disponible", money(total_disponible))

    if excedidos:
        st.error(f"⚠ Hay {excedidos} mayorista(s) excedidos de crédito.")

    st.divider()

    st.subheader("Listado de mayoristas")

    for c in mayoristas:
        disponible = float(c.get("credito_disponible") or 0)
        saldo = float(c.get("saldo_cuenta_corriente") or 0)
        limite = float(c.get("limite_credito") or 0)
        excedido = bool(c.get("excedido"))

        with st.container(border=True):
            titulo = _nombre_completo(c)
            estado = "🔴 Excedido" if excedido else "🟢 Normal"

            st.markdown(f"### {titulo} — {estado}")

            a, b, ccol, d = st.columns(4)
            a.metric("Límite crédito", money(limite))
            b.metric("Usado", money(saldo))
            ccol.metric("Disponible", money(disponible))
            d.write(f"📞 {c.get('telefono') or '-'}")
            d.write(f"📍 {c.get('direccion') or '-'}")

            cliente_id = c.get("id")

            with st.expander("Ver / cargar movimientos"):
                try:
                    movimientos = (
                        db.table(table("credito_movimientos"))
                        .select("*")
                        .eq("cliente_id", cliente_id)
                        .order("fecha", desc=True)
                        .execute()
                        .data
                    )
                except Exception:
                    movimientos = []
                    st.warning(
                        "No pude leer namnam_credito_movimientos. "
                        "Verificá que ejecutaste el SQL correspondiente."
                    )

                with st.form(f"mov_credito_{cliente_id}", clear_on_submit=True):
                    m1, m2, m3 = st.columns([2, 2, 4])

                    tipo = m1.selectbox(
                        "Tipo",
                        ["Credito otorgado", "Consumo", "Pago", "Ajuste"],
                        key=f"tipo_{cliente_id}"
                    )

                    importe = m2.number_input(
                        "Importe",
                        min_value=0.0,
                        step=100.0,
                        key=f"importe_{cliente_id}"
                    )

                    obs = m3.text_input(
                        "Observaciones",
                        key=f"obs_{cliente_id}"
                    )

                    if st.form_submit_button("Registrar movimiento"):
                        if importe <= 0:
                            st.warning("El importe debe ser mayor a cero.")
                        else:
                            db.table(table("credito_movimientos")).insert({
                                "cliente_id": cliente_id,
                                "tipo": tipo,
                                "importe": importe,
                                "observaciones": obs.strip()
                            }).execute()

                            if tipo == "Credito otorgado":
                                nuevo_limite = limite + importe
                                db.table(table("clientes")).update({
                                    "limite_credito": nuevo_limite
                                }).eq("id", cliente_id).execute()

                            elif tipo == "Consumo":
                                nuevo_saldo = saldo + importe
                                db.table(table("clientes")).update({
                                    "saldo_cuenta_corriente": nuevo_saldo
                                }).eq("id", cliente_id).execute()

                            elif tipo == "Pago":
                                nuevo_saldo = saldo - importe
                                db.table(table("clientes")).update({
                                    "saldo_cuenta_corriente": nuevo_saldo
                                }).eq("id", cliente_id).execute()

                            elif tipo == "Ajuste":
                                nuevo_saldo = saldo + importe
                                db.table(table("clientes")).update({
                                    "saldo_cuenta_corriente": nuevo_saldo
                                }).eq("id", cliente_id).execute()

                            st.success("Movimiento registrado.")
                            st.rerun()

                if movimientos:
                    df = pd.DataFrame(movimientos)
                    cols = [x for x in ["fecha", "tipo", "importe", "observaciones"] if x in df.columns]
                    st.dataframe(df[cols], use_container_width=True, hide_index=True)
                else:
                    st.info("Este cliente todavía no tiene movimientos.")
