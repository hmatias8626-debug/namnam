import json
from datetime import time

import streamlit as st

from services.auth import current_user
from services.db import require_db
from services.ui import header


DIAS = [("lun", "Lunes"), ("mar", "Martes"), ("mie", "Miércoles"), ("jue", "Jueves"), ("vie", "Viernes"), ("sab", "Sábado"), ("dom", "Domingo")]


def _time_to_str(v):
    if not v:
        return ""
    if isinstance(v, str):
        return v[:5]
    try:
        return v.strftime("%H:%M")
    except Exception:
        return ""


def _str_to_time(v, default=None):
    if not v:
        return default
    try:
        hh, mm = str(v)[:5].split(":")
        return time(int(hh), int(mm))
    except Exception:
        return default


def _get_config(db, clave, default=""):
    res = db.table("namnam_configuracion").select("*").eq("clave", clave).execute().data or []
    return res[0].get("valor") if res else default


def _set_config(db, clave, valor):
    existe = db.table("namnam_configuracion").select("*").eq("clave", clave).execute().data or []
    if existe:
        db.table("namnam_configuracion").update({"valor": str(valor)}).eq("clave", clave).execute()
    else:
        db.table("namnam_configuracion").insert({"clave": clave, "valor": str(valor)}).execute()


def _json_config(db, clave, default):
    try:
        valor = _get_config(db, clave, "")
        return json.loads(valor) if valor else default
    except Exception:
        return default


def _horarios_reparto_default():
    base = {}
    for k, _ in DIAS:
        base[k] = {"activo": True, "t1_desde": "17:00", "t1_hasta": "20:00", "t2_desde": "", "t2_hasta": ""}
    base["sab"] = {"activo": True, "t1_desde": "11:00", "t1_hasta": "13:00", "t2_desde": "18:00", "t2_hasta": "20:00"}
    base["dom"] = {"activo": True, "t1_desde": "11:00", "t1_hasta": "12:00", "t2_desde": "", "t2_hasta": ""}
    return base


def _resumen_horarios(horarios):
    partes = []
    for key, nombre in DIAS:
        h = horarios.get(key, {})
        if not h.get("activo"):
            partes.append(f"{nombre}: sin reparto")
            continue
        turnos = []
        if h.get("t1_desde") and h.get("t1_hasta"):
            turnos.append(f"{h.get('t1_desde')} a {h.get('t1_hasta')}")
        if h.get("t2_desde") and h.get("t2_hasta"):
            turnos.append(f"{h.get('t2_desde')} a {h.get('t2_hasta')}")
        partes.append(f"{nombre}: {' y '.join(turnos) if turnos else 'sin horario'}")
    return "\n".join(partes)


def _form_horarios(prefix, horarios):
    nuevo = {}
    for key, nombre in DIAS:
        h = horarios.get(key, {})
        with st.container(border=True):
            activo = st.toggle(nombre, value=bool(h.get("activo", True)), key=f"{prefix}_{key}_activo")
            c1, c2, c3, c4 = st.columns(4)
            t1_desde = c1.time_input("Turno 1 desde", value=_str_to_time(h.get("t1_desde"), time(17, 0)), key=f"{prefix}_{key}_t1d", disabled=not activo)
            t1_hasta = c2.time_input("Turno 1 hasta", value=_str_to_time(h.get("t1_hasta"), time(20, 0)), key=f"{prefix}_{key}_t1h", disabled=not activo)
            turno2_on = st.toggle("Tiene segundo turno", value=bool(h.get("t2_desde") and h.get("t2_hasta")), key=f"{prefix}_{key}_t2on", disabled=not activo)
            t2_desde = c3.time_input("Turno 2 desde", value=_str_to_time(h.get("t2_desde"), time(18, 0)), key=f"{prefix}_{key}_t2d", disabled=(not activo or not turno2_on))
            t2_hasta = c4.time_input("Turno 2 hasta", value=_str_to_time(h.get("t2_hasta"), time(20, 0)), key=f"{prefix}_{key}_t2h", disabled=(not activo or not turno2_on))
            nuevo[key] = {
                "activo": activo,
                "t1_desde": _time_to_str(t1_desde) if activo else "",
                "t1_hasta": _time_to_str(t1_hasta) if activo else "",
                "t2_desde": _time_to_str(t2_desde) if activo and turno2_on else "",
                "t2_hasta": _time_to_str(t2_hasta) if activo and turno2_on else "",
            }
    return nuevo


def render():
    user = current_user() or {}
    if user.get("rol") != "admin":
        st.error("Solo el administrador puede ver configuración.")
        return
    header("⚙️ Configuración", "Datos generales de pedidos online")
    db = require_db()
    tab_general, tab_envios = st.tabs(["⚙️ General", "🚚 Envíos y reparto"])
    with tab_general:
        whatsapp_actual = _get_config(db, "whatsapp_pedidos", "5493812019770")
        st.subheader("📲 WhatsApp de pedidos")
        whatsapp = st.text_input("Número que recibe los pedidos", value=whatsapp_actual, help="Formato internacional sin + ni espacios. Ej: 5493812019770")
        if st.button("Guardar WhatsApp"):
            _set_config(db, "whatsapp_pedidos", whatsapp.strip())
            st.success("WhatsApp guardado.")
            st.rerun()
    with tab_envios:
        st.subheader("🚚 Configuración de envío")
        permitir_envio = st.toggle("Permitir envío a domicilio", value=_get_config(db, "permitir_envio", "true").lower() == "true")
        permitir_retiro = st.toggle("Permitir retiro en local", value=_get_config(db, "permitir_retiro", "true").lower() == "true")
        costo_envio = st.number_input("Costo de envío si NO supera el mínimo", min_value=0.0, step=500.0, value=float(_get_config(db, "costo_envio", "0") or 0))
        minimo_envio_gratis = st.number_input("Envío gratis desde", min_value=0.0, step=1000.0, value=float(_get_config(db, "minimo_envio_gratis", "0") or 0))
        aclaracion_envio = st.text_area("Mensaje aclaratorio para envío", value=_get_config(db, "mensaje_aclaratorio_envio", "Los horarios son orientativos y se confirman por WhatsApp."))
        st.divider()
        st.subheader("🕒 Horarios de reparto")
        horarios = _json_config(db, "horarios_reparto_json", _horarios_reparto_default())
        nuevos_horarios = _form_horarios("reparto", horarios)
        st.markdown("#### Vista previa")
        st.info(_resumen_horarios(nuevos_horarios))
        if st.button("Guardar configuración de envío"):
            _set_config(db, "permitir_envio", str(permitir_envio).lower())
            _set_config(db, "permitir_retiro", str(permitir_retiro).lower())
            _set_config(db, "costo_envio", costo_envio)
            _set_config(db, "minimo_envio_gratis", minimo_envio_gratis)
            _set_config(db, "mensaje_aclaratorio_envio", aclaracion_envio.strip())
            _set_config(db, "horarios_reparto", _resumen_horarios(nuevos_horarios))
            _set_config(db, "horarios_reparto_json", json.dumps(nuevos_horarios, ensure_ascii=False))
            st.success("Configuración de envío guardada.")
            st.rerun()
