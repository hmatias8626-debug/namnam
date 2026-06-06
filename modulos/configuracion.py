import streamlit as st

from services.auth import current_user
from services.db import require_db
from services.ui import header


def _get_config(db, clave, default=""):
    res = (
        db.table("namnam_configuracion")
        .select("*")
        .eq("clave", clave)
        .execute()
        .data
        or []
    )
    return res[0].get("valor") if res else default


def _set_config(db, clave, valor):
    existe = (
        db.table("namnam_configuracion")
        .select("*")
        .eq("clave", clave)
        .execute()
        .data
        or []
    )

    if existe:
        db.table("namnam_configuracion").update({
            "valor": valor
        }).eq("clave", clave).execute()
    else:
        db.table("namnam_configuracion").insert({
            "clave": clave,
            "valor": valor,
        }).execute()


def render():
    user = current_user() or {}
    rol = user.get("rol")

    if rol != "admin":
        st.error("Solo el administrador puede ver configuración.")
        return

    header("⚙️ Configuración", "Datos generales de pedidos online")

    db = require_db()

    whatsapp_actual = _get_config(db, "whatsapp_pedidos", "5493812019770")
    reparto_actual = _get_config(
        db,
        "horario_reparto",
        "Repartos disponibles según zona y disponibilidad. El horario será confirmado por WhatsApp al recibir el pedido."
    )

    st.subheader("📲 WhatsApp de pedidos")

    whatsapp = st.text_input(
        "Número que recibe los pedidos",
        value=whatsapp_actual,
        help="Usar formato internacional sin + ni espacios. Ej: 5493812019770"
    )

    st.caption("Ejemplo Argentina: 549 + código de área + número.")

    st.divider()

    st.subheader("🚚 Horarios / aclaración de reparto")

    horario_reparto = st.text_area(
        "Texto que verá el cliente cuando elige envío",
        value=reparto_actual,
        height=120,
    )

    if st.button("Guardar configuración"):
        _set_config(db, "whatsapp_pedidos", whatsapp.strip())
        _set_config(db, "horario_reparto", horario_reparto.strip())

        st.success("Configuración guardada.")
        st.rerun()
