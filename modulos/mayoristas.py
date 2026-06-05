import pandas as pd
import streamlit as st
from services.db import require_db, money
from services.ui import header

def _nombre_completo(cliente: dict) -> str:
    nombre = cliente.get("nombre") or ""
    apellido = cliente.get("apellido") or ""
    completo = f"{nombre} {apellido}".strip()
    return completo or f"Cliente #{cliente.get('id')}"

def render():
    header("🏪 Mayoristas", "Saldo disponible, consumos e historial")
    db = require_db()

    try:
        mayoristas = db.table("namnam_mayoristas_credito").select("*").execute().data
    except Exception as e:
        st.warning("No pude leer la vista namnam_mayoristas_credito. Ejecutá el SQL actualizado en Supabase.")
        st.exception(e)
        return

    if not mayoristas:
        st.info("Todavía no hay clientes mayoristas cargados.")
        st.caption("Cargalos desde Clientes seleccionando tipo Mayorista.")
        return

    total_saldo = sum(float(c.get("saldo_cuenta_corriente") or 0) for c in mayoristas)
    excedidos = sum(1 for c in mayoristas if c.get("excedido"))

    c1, c2 = st.columns(2)
    c1.metric("Mayoristas", len(mayoristas))
    c2.metric("Saldo total disponible", money(total_saldo))

    if excedidos:
        st.error(f"⚠ Hay {excedidos} mayorista(s) con saldo negativo.")

    st.divider()
    st.subheader("Listado de mayoristas")

    for c in mayoristas:
        saldo = float(c.get("saldo_cuenta_corriente") or 0)
        excedido = bool(c.get("excedido"))

        with st.container(border=True):
            titulo = _nombre_completo(c)
            estado = "🔴 Debe" if excedido else "🟢 Con saldo"
            st.markdown(f"### {titulo} — {estado}")

            a, b, d = st.columns(3)
            if saldo < 0:
                a.error(f"Debe: {money(abs(saldo))}")
                b.metric("Saldo disponible", money(saldo))
            else:
                a.success(f"Saldo disponible: {money(saldo)}")
                b.metric("Saldo a favor", money(saldo))

            d.write(f"📞 {c.get('telefono') or '-'}")
            d.write(f"📍 {c.get('direccion') or '-'}")

            cliente_id = c.get("id")

            with st.expander("Historial de movimientos"):
                try:
                    movimientos = (
                        db.table("namnam_credito_movimientos")
                        .select("*")
                        .eq("cliente_id", cliente_id)
                        .order("fecha", desc=True)
                        .execute()
                        .data
                    )
                except Exception as e:
                    movimientos = []
                    st.warning("No pude leer namnam_credito_movimientos.")
                    st.exception(e)

                if movimientos:
                    df = pd.DataFrame(movimientos)
                    cols = [x for x in ["fecha", "tipo", "importe", "observaciones"] if x in df.columns]
                    st.dataframe(df[cols], use_container_width=True, hide_index=True)
                else:
                    st.info("Este cliente todavía no tiene movimientos.")
