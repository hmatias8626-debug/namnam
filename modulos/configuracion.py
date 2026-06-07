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
        db.table("namnam_configuracion").update({"valor": str(valor)}).eq("clave", clave).execute()
    else:
        db.table("namnam_configuracion").insert({"clave": clave, "valor": str(valor)}).execute()


def _as_bool(valor, default=True):
    if valor is None:
        return default
    return str(valor).strip().lower() in ["1", "true", "si", "sí", "yes", "on"]


def _as_float(valor, default=0):
    try:
        txt = str(valor or default).replace("$", "").replace(" ", "").replace(".", "").replace(",", ".")
        return float(txt or 0)
    except Exception:
        return float(default or 0)


def render():
    user = current_user() or {}
    rol = user.get("rol")

    if rol != "admin":
        st.error("Solo el administrador puede ver configuración.")
        return

    header("⚙️ Configuración", "Datos generales de pedidos online")

    db = require_db()

    whatsapp_actual = _get_config(db, "whatsapp_pedidos", "5493812019770")
    permitir_envio_actual = _as_bool(_get_config(db, "permitir_envio", "1"), True)
    permitir_retiro_actual = _as_bool(_get_config(db, "permitir_retiro", "1"), True)
    costo_envio_actual = _as_float(_get_config(db, "costo_envio", "0"), 0)
    envio_gratis_actual = _as_float(_get_config(db, "envio_gratis_desde", "0"), 0)
    reparto_actual = _get_config(
        db,
        "horario_reparto",
        "Lunes a viernes: 17 a 20 hs\nSábados: 11 a 13 hs y 18 a 20 hs\nDomingos: 11 a 12 hs",
    )
    aclaratorio_actual = _get_config(db, "texto_aclaratorio_entrega", "Los horarios son orientativos y se confirman por WhatsApp.")

    st.subheader("📲 WhatsApp de pedidos")
    whatsapp = st.text_input("Número que recibe los pedidos", value=whatsapp_actual, help="Usar formato internacional sin + ni espacios. Ej: 5493812019770")
    st.caption("Ejemplo Argentina: 549 + código de área + número.")

    st.divider()
    st.subheader("🚚 Envíos")

    permitir_envio = st.toggle("Permitir envío a domicilio", value=permitir_envio_actual)
    permitir_retiro = st.toggle("Permitir retiro en local", value=permitir_retiro_actual)

    c1, c2 = st.columns(2)
    with c1:
        costo_envio = st.number_input("Costo de envío", min_value=0.0, step=100.0, value=float(costo_envio_actual))
    with c2:
        envio_gratis_desde = st.number_input("Envío gratis desde", min_value=0.0, step=100.0, value=float(envio_gratis_actual), help="Si el subtotal de productos supera este monto, el envío queda sin cargo. Si ponés 0, no se aplica envío gratis automático.")

    horario_reparto = st.text_area("Horarios de reparto", value=reparto_actual, height=130)
    texto_aclaratorio = st.text_area("Mensaje aclaratorio de entrega", value=aclaratorio_actual, height=90)

    if st.button("Guardar configuración", use_container_width=True):
        _set_config(db, "whatsapp_pedidos", whatsapp.strip())
        _set_config(db, "permitir_envio", "1" if permitir_envio else "0")
        _set_config(db, "permitir_retiro", "1" if permitir_retiro else "0")
        _set_config(db, "costo_envio", costo_envio)
        _set_config(db, "envio_gratis_desde", envio_gratis_desde)
        _set_config(db, "horario_reparto", horario_reparto.strip())
        _set_config(db, "texto_aclaratorio_entrega", texto_aclaratorio.strip())
        st.success("Configuración guardada.")
        st.rerun()
