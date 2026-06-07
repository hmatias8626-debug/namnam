import json
from datetime import time

import streamlit as st

from services.auth import current_user
from services.db import require_db
from services.ui import header


DIAS = [
    ("lun", "Lunes"),
    ("mar", "Martes"),
    ("mie", "Miércoles"),
    ("jue", "Jueves"),
    ("vie", "Viernes"),
    ("sab", "Sábado"),
    ("dom", "Domingo"),
]


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


def _horarios_default():
    base = {}
    for k, _ in DIAS:
        base[k] = {
            "activo": k != "dom",
            "t1_desde": "10:00",
            "t1_hasta": "13:00",
            "t2_desde": "17:00" if k != "dom" else "",
            "t2_hasta": "20:00" if k != "dom" else "",
        }
    base["dom"] = {"activo": True, "t1_desde": "10:00", "t1_hasta": "12:00", "t2_desde": "", "t2_hasta": ""}
    return base


def _leer_json(valor, default):
    try:
        if isinstance(valor, dict):
            return valor
        if not valor:
            return default
        return json.loads(valor)
    except Exception:
        return default


def _resumen_horarios(horarios: dict) -> str:
    partes = []
    for key, nombre in DIAS:
        h = horarios.get(key, {})
        if not h.get("activo"):
            partes.append(f"{nombre}: cerrado")
            continue
        turnos = []
        if h.get("t1_desde") and h.get("t1_hasta"):
            turnos.append(f"{h.get('t1_desde')} a {h.get('t1_hasta')}")
        if h.get("t2_desde") and h.get("t2_hasta"):
            turnos.append(f"{h.get('t2_desde')} a {h.get('t2_hasta')}")
        partes.append(f"{nombre}: {' y '.join(turnos) if turnos else 'sin horario'}")
    return "\n".join(partes)


def _form_horarios(prefix: str, horarios: dict) -> dict:
    st.caption("Cargá hasta 2 turnos por día. Si está cerrado, desactivá el día.")
    nuevo = {}
    for key, nombre in DIAS:
        actual = horarios.get(key, {})
        with st.container(border=True):
            activo = st.toggle(nombre, value=bool(actual.get("activo", True)), key=f"{prefix}_{key}_activo")
            c1, c2, c3, c4 = st.columns(4)
            t1_desde = c1.time_input("Turno 1 desde", value=_str_to_time(actual.get("t1_desde"), time(10, 0)), key=f"{prefix}_{key}_t1d", disabled=not activo)
            t1_hasta = c2.time_input("Turno 1 hasta", value=_str_to_time(actual.get("t1_hasta"), time(13, 0)), key=f"{prefix}_{key}_t1h", disabled=not activo)
            tiene_turno2 = st.toggle("Tiene segundo turno", value=bool(actual.get("t2_desde") and actual.get("t2_hasta")), key=f"{prefix}_{key}_t2_on", disabled=not activo)
            t2_desde = c3.time_input("Turno 2 desde", value=_str_to_time(actual.get("t2_desde"), time(17, 0)), key=f"{prefix}_{key}_t2d", disabled=(not activo or not tiene_turno2))
            t2_hasta = c4.time_input("Turno 2 hasta", value=_str_to_time(actual.get("t2_hasta"), time(20, 0)), key=f"{prefix}_{key}_t2h", disabled=(not activo or not tiene_turno2))
            nuevo[key] = {
                "activo": activo,
                "t1_desde": _time_to_str(t1_desde) if activo else "",
                "t1_hasta": _time_to_str(t1_hasta) if activo else "",
                "t2_desde": _time_to_str(t2_desde) if activo and tiene_turno2 else "",
                "t2_hasta": _time_to_str(t2_hasta) if activo and tiene_turno2 else "",
            }
    return nuevo


def _leer_locales(db):
    return db.table("namnam_locales").select("*").order("id").execute().data or []


def render():
    user = current_user() or {}
    if user.get("rol") != "admin":
        st.error("Solo el administrador puede gestionar locales.")
        return

    header("🏪 Locales", "Puntos de retiro y horarios de atención")
    db = require_db()

    tab_nuevo, tab_lista, tab_feriados = st.tabs(["➕ Nuevo local", "🏪 Locales cargados", "📅 Feriados / excepciones"])

    with tab_nuevo:
        st.subheader("Agregar local / punto de retiro")
        nombre = st.text_input("Nombre", placeholder="Ej: Local Bulnes 90")
        direccion = st.text_input("Dirección", placeholder="Ej: Bulnes 90")
        activo = st.toggle("Activo", value=True)
        st.markdown("### Horarios de atención")
        horarios = _form_horarios("nuevo_local", _horarios_default())
        st.markdown("#### Vista previa")
        st.info(_resumen_horarios(horarios))
        if st.button("Guardar local"):
            if not nombre.strip():
                st.warning("Falta el nombre del local.")
            else:
                db.table("namnam_locales").insert({
                    "nombre": nombre.strip(),
                    "direccion": direccion.strip(),
                    "horarios": _resumen_horarios(horarios),
                    "horarios_json": json.dumps(horarios, ensure_ascii=False),
                    "activo": activo,
                }).execute()
                st.success("Local guardado.")
                st.rerun()

    with tab_lista:
        st.subheader("Locales disponibles")
        try:
            locales = _leer_locales(db)
        except Exception as e:
            st.error("No pude leer locales. Ejecutá el SQL de actualización.")
            st.exception(e)
            return
        if not locales:
            st.info("Todavía no hay locales cargados.")
            return
        for local in locales:
            horarios_actuales = _leer_json(local.get("horarios_json"), _horarios_default())
            with st.container(border=True):
                st.markdown(f"### 🏪 {local.get('nombre')}")
                st.write(f"**Dirección:** {local.get('direccion') or '-'}")
                st.caption("Horarios actuales:")
                st.code(local.get("horarios") or _resumen_horarios(horarios_actuales), language=None)
                activo = st.toggle("Activo", value=bool(local.get("activo", True)), key=f"local_activo_{local['id']}")
                with st.expander("Editar local"):
                    nuevo_nombre = st.text_input("Nombre", value=local.get("nombre") or "", key=f"local_nombre_{local['id']}")
                    nueva_direccion = st.text_input("Dirección", value=local.get("direccion") or "", key=f"local_dir_{local['id']}")
                    st.markdown("#### Horarios")
                    nuevos_horarios = _form_horarios(f"edit_local_{local['id']}", horarios_actuales)
                    st.markdown("#### Vista previa")
                    st.info(_resumen_horarios(nuevos_horarios))
                    col_g, col_b = st.columns([1, 1])
                    if col_g.button("Guardar cambios", key=f"guardar_local_{local['id']}"):
                        db.table("namnam_locales").update({
                            "nombre": nuevo_nombre.strip(),
                            "direccion": nueva_direccion.strip(),
                            "horarios": _resumen_horarios(nuevos_horarios),
                            "horarios_json": json.dumps(nuevos_horarios, ensure_ascii=False),
                            "activo": activo,
                        }).eq("id", local["id"]).execute()
                        st.success("Local actualizado.")
                        st.rerun()
                    if col_b.button("Eliminar local", key=f"borrar_local_{local['id']}"):
                        db.table("namnam_locales").delete().eq("id", local["id"]).execute()
                        st.success("Local eliminado.")
                        st.rerun()

    with tab_feriados:
        st.subheader("Feriados y horarios especiales")
        st.info("Cargá feriados o días especiales. Después lo usamos para avisar o bloquear horarios en el catálogo.")
        try:
            excepciones = db.table("namnam_horarios_excepciones").select("*").order("fecha").execute().data or []
        except Exception as e:
            st.error("No pude leer excepciones. Ejecutá el SQL de actualización.")
            st.exception(e)
            return
        with st.form("nueva_excepcion"):
            fecha = st.date_input("Fecha")
            descripcion = st.text_input("Descripción", placeholder="Ej: Navidad, feriado, horario especial")
            cerrado = st.toggle("Cerrado todo el día", value=True)
            c1, c2, c3, c4 = st.columns(4)
            desde1 = c1.time_input("Turno 1 desde", value=time(10, 0), disabled=cerrado)
            hasta1 = c2.time_input("Turno 1 hasta", value=time(13, 0), disabled=cerrado)
            tiene_turno2 = st.toggle("Tiene segundo turno", value=False, disabled=cerrado)
            desde2 = c3.time_input("Turno 2 desde", value=time(17, 0), disabled=(cerrado or not tiene_turno2))
            hasta2 = c4.time_input("Turno 2 hasta", value=time(20, 0), disabled=(cerrado or not tiene_turno2))
            guardar = st.form_submit_button("Guardar excepción")
            if guardar:
                horarios_json = {
                    "cerrado": cerrado,
                    "t1_desde": _time_to_str(desde1) if not cerrado else "",
                    "t1_hasta": _time_to_str(hasta1) if not cerrado else "",
                    "t2_desde": _time_to_str(desde2) if not cerrado and tiene_turno2 else "",
                    "t2_hasta": _time_to_str(hasta2) if not cerrado and tiene_turno2 else "",
                }
                db.table("namnam_horarios_excepciones").insert({
                    "fecha": fecha.isoformat(),
                    "descripcion": descripcion.strip(),
                    "cerrado": cerrado,
                    "horarios_json": json.dumps(horarios_json, ensure_ascii=False),
                }).execute()
                st.success("Excepción guardada.")
                st.rerun()
        if excepciones:
            st.markdown("### Excepciones cargadas")
            for ex in excepciones:
                with st.container(border=True):
                    st.write(f"**{ex.get('fecha')}** - {ex.get('descripcion') or ''}")
                    st.write("Cerrado" if ex.get("cerrado") else "Horario especial")
                    if st.button("Eliminar", key=f"borrar_ex_{ex['id']}"):
                        db.table("namnam_horarios_excepciones").delete().eq("id", ex["id"]).execute()
                        st.rerun()
        else:
            st.info("Todavía no hay feriados o excepciones cargadas.")
