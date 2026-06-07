import urllib.parse

import pandas as pd
import streamlit as st

from services.db import require_db, fetch_table, table, money


WHATSAPP_NEGOCIO_DEFAULT = "5493812019770"

PUNTOS_RETIRO_DEFAULT = {
    "Fábrica": {
        "direccion": "Fábrica Ñam Ñam",
        "horarios": "Consultar horarios disponibles para retiro.",
    },
    "Local Bulnes 90": {
        "direccion": "Bulnes 90",
        "horarios": "Consultar horarios disponibles para retiro.",
    },
    "Local Pje Ignacio Bass 3779": {
        "direccion": "Pje Ignacio Bass 3779",
        "horarios": "Consultar horarios disponibles para retiro.",
    },
}

HORARIO_REPARTO_DEFAULT = """
Repartos disponibles según zona y disponibilidad.
El horario será confirmado por WhatsApp al recibir el pedido.
"""



def _get_config(db, clave, default=""):
    try:
        res = (
            db.table("namnam_configuracion")
            .select("*")
            .eq("clave", clave)
            .execute()
            .data
            or []
        )
        return res[0].get("valor") if res else default
    except Exception:
        return default


def _leer_locales_retiro(db):
    try:
        locales = (
            db.table("namnam_locales")
            .select("*")
            .eq("activo", True)
            .order("id")
            .execute()
            .data
            or []
        )

        if not locales:
            return PUNTOS_RETIRO_DEFAULT

        return {
            l.get("nombre"): {
                "direccion": l.get("direccion") or "",
                "horarios": l.get("horarios") or "",
            }
            for l in locales
            if l.get("nombre")
        }
    except Exception:
        return PUNTOS_RETIRO_DEFAULT

def _float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _familia_producto(p):
    familia = (
        p.get("familia")
        or p.get("categoria")
        or p.get("categoría")
        or p.get("rubro")
        or p.get("grupo")
        or "Otros"
    )
    familia = str(familia).strip()
    return familia if familia else "Otros"


def _emoji_familia(familia):
    f = familia.lower()
    if "sorrent" in f:
        return "🍝"
    if "tarta" in f:
        return "🥧"
    if "ñoqui" in f or "noqui" in f:
        return "🥔"
    if "pizza" in f:
        return "🍕"
    if "sfija" in f:
        return "🥟"
    if "bombita" in f:
        return "🧆"
    if "sandwich" in f or "sándwich" in f:
        return "🥪"
    if "torta" in f:
        return "🍰"
    return "📦"


def _ordenar_familias(familias):
    preferidas = [
        "Sorrentinos",
        "Sorrentinos Premium",
        "Tartas",
        "Tartas Individuales",
        "Tartas Individuales Premium",
        "Tartas Integrales",
        "Ñoquis",
        "Ñoquis comunes",
        "Ñoquis rellenos",
        "Pizzas",
        "Sfijas",
        "Bombitas de papa",
        "Sandwiches de miga",
        "Torta salada",
        "Otros",
    ]

    ordenadas = []
    usadas = set()

    for pref in preferidas:
        for f in familias.keys():
            if f.lower() == pref.lower() and f not in usadas:
                ordenadas.append(f)
                usadas.add(f)

    for f in sorted(familias.keys()):
        if f not in usadas:
            ordenadas.append(f)

    return ordenadas


def _init_cart():
    if "cliente_productos" not in st.session_state:
        st.session_state["cliente_productos"] = {}
    if "cliente_promos" not in st.session_state:
        st.session_state["cliente_promos"] = {}
    if "pedido_online_confirmado" not in st.session_state:
        st.session_state["pedido_online_confirmado"] = False
    if "pedido_online_wa_url" not in st.session_state:
        st.session_state["pedido_online_wa_url"] = ""
    if "pedido_online_resumen" not in st.session_state:
        st.session_state["pedido_online_resumen"] = None
    if "catalogo_seccion" not in st.session_state:
        st.session_state["catalogo_seccion"] = "Categorías"


def _get_qty(tipo, item_id):
    _init_cart()
    store = "cliente_promos" if tipo == "promo" else "cliente_productos"
    return _float(st.session_state[store].get(str(item_id), 0))


def _set_qty(tipo, item_id, value):
    _init_cart()
    store = "cliente_promos" if tipo == "promo" else "cliente_productos"
    key = str(item_id)
    value = _float(value)

    if value <= 0:
        st.session_state[store].pop(key, None)
    else:
        st.session_state[store][key] = value


def _change_qty(tipo, item_id, delta):
    actual = _get_qty(tipo, item_id)
    _set_qty(tipo, item_id, max(0, actual + delta))


def _remove_qty(tipo, item_id):
    _set_qty(tipo, item_id, 0)


def _set_qty_from_input(tipo, item_id, key):
    _set_qty(tipo, item_id, st.session_state.get(key, 0))


def _set_seccion(seccion):
    st.session_state["catalogo_seccion"] = seccion


def _limpiar_carrito():
    st.session_state["cliente_productos"] = {}
    st.session_state["cliente_promos"] = {}
    st.session_state["pedido_online_confirmado"] = False
    st.session_state["pedido_online_wa_url"] = ""
    st.session_state["pedido_online_resumen"] = None


def _leer_promos(db):
    try:
        return (
            db.table("namnam_promos")
            .select("*")
            .eq("activo", True)
            .order("id")
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _leer_detalle_promo(db, promo_id):
    try:
        return (
            db.table("namnam_promos_detalle")
            .select("*")
            .eq("promo_id", promo_id)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _armar_items(productos, promos):
    items = []

    for p in productos:
        cant = _get_qty("producto", p["id"])
        precio = _float(p.get("precio_venta"))

        if cant > 0:
            items.append({
                "tipo": "producto",
                "producto_id": p["id"],
                "producto_nombre": p.get("nombre"),
                "cantidad": cant,
                "precio_unitario": precio,
                "subtotal": cant * precio,
                "promo_id": None,
            })

    for promo in promos:
        cant = _get_qty("promo", promo["id"])
        precio = _float(promo.get("precio"))

        if cant > 0:
            items.append({
                "tipo": "promo",
                "producto_id": None,
                "producto_nombre": promo.get("nombre"),
                "cantidad": cant,
                "precio_unitario": precio,
                "subtotal": cant * precio,
                "promo_id": promo["id"],
            })

    return items


def _mensaje_whatsapp(pedido_id, nombre, telefono, tipo_entrega, punto_retiro, direccion, barrio, referencia, fecha, hora, forma_pago, items, total):
    lineas = [
        f"🍝 Nuevo pedido Ñam Ñam #{pedido_id}",
        "",
        f"Cliente: {nombre}",
        f"Teléfono: {telefono}",
        f"Pago: {forma_pago}",
        "",
        f"Entrega: {tipo_entrega}",
    ]

    if tipo_entrega == "Retira en local":
        lineas.append(f"Punto de retiro: {punto_retiro}")
    else:
        lineas.append(f"Dirección: {direccion}")
        if barrio:
            lineas.append(f"Barrio: {barrio}")
        if referencia:
            lineas.append(f"Referencia: {referencia}")

    lineas += [
        f"Fecha: {fecha or 'A coordinar'}",
        f"Hora: {hora or 'A coordinar'}",
        "",
        "Pedido:",
    ]

    for it in items:
        lineas.append(f"- {it['cantidad']:g} x {it['producto_nombre']} = {money(it['subtotal'])}")

    lineas += ["", f"Total: {money(total)}"]

    return "\n".join(lineas)


def _css():
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        display: none !important;
    }

    .main .block-container {
        max-width: 980px !important;
        padding-top: 1.5rem !important;
        padding-bottom: 8rem !important;
    }

    h1, h2, h3, label, p, span {
        color: #FFF7E6 !important;
    }

    .stButton > button {
        background-color: #D89B1D !important;
        color: #111111 !important;
        border-radius: 14px !important;
        font-weight: 900 !important;
        border: 0 !important;
    }

    input, textarea {
        background-color: #FFF7E6 !important;
        color: #111111 !important;
        font-weight: 800 !important;
    }

    div[data-baseweb="select"] span {
        color: #111111 !important;
    }

    .wa-alert {
        background: #ffffff !important;
        color: #111111 !important;
        border: 3px solid #25D366 !important;
        border-radius: 18px !important;
        padding: 22px !important;
        margin: 18px 0 !important;
        box-shadow: 0 8px 24px rgba(0,0,0,.35) !important;
        text-align: center !important;
    }

    .wa-alert-title {
        color: #111111 !important;
        font-size: 22px !important;
        font-weight: 1000 !important;
        margin-bottom: 8px !important;
        text-shadow: none !important;
    }

    .wa-alert-text {
        color: #111111 !important;
        font-size: 16px !important;
        font-weight: 800 !important;
        margin-bottom: 18px !important;
        text-shadow: none !important;
    }

    .wa-alert a {
        display: inline-block !important;
        width: 92% !important;
        max-width: 460px !important;
        background: #25D366 !important;
        color: #000000 !important;
        padding: 17px 24px !important;
        border-radius: 14px !important;
        text-decoration: none !important;
        font-size: 22px !important;
        font-weight: 1000 !important;
        border: 3px solid #0b7a32 !important;
        box-shadow: 0 5px 16px rgba(0,0,0,.35) !important;
        text-shadow: none !important;
    }

    .wa-alert a:hover {
        background: #1ebe5d !important;
        color: #000000 !important;
    }

    /* Vista cliente más compacta para celular */
    h1 {
        font-size: 30px !important;
        margin-bottom: 0.2rem !important;
    }

    h2 {
        font-size: 23px !important;
        margin-top: 0.6rem !important;
        margin-bottom: 0.6rem !important;
    }

    h3 {
        font-size: 18px !important;
        margin-top: 0.25rem !important;
        margin-bottom: 0.25rem !important;
    }

    .main .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }

    .producto-nombre {
        color: #FFF7E6 !important;
        font-size: 16px !important;
        font-weight: 900 !important;
        line-height: 1.15 !important;
        margin-bottom: 2px !important;
    }

    .producto-info {
        color: #FFF7E6 !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        opacity: .95 !important;
        margin-bottom: 6px !important;
    }

    .categoria-card {
        color: #FFF7E6 !important;
        font-size: 17px !important;
        font-weight: 950 !important;
        line-height: 1.15 !important;
        margin-bottom: 2px !important;
    }

    .categoria-sub {
        color: #FFF7E6 !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        opacity: .9 !important;
    }

    .qty-num {
        color: #FFF7E6 !important;
        font-size: 21px !important;
        font-weight: 1000 !important;
        text-align: center !important;
        padding-top: 8px !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        padding-top: 0.45rem !important;
        padding-bottom: 0.45rem !important;
    }

    @media (max-width: 650px) {
        .main .block-container {
            padding-top: 0.75rem !important;
            padding-left: 0.45rem !important;
            padding-right: 0.45rem !important;
        }

        h1 {
            font-size: 26px !important;
        }

        h2 {
            font-size: 20px !important;
        }

        .producto-nombre {
            font-size: 15px !important;
        }

        .producto-info {
            font-size: 12px !important;
        }

        .categoria-card {
            font-size: 16px !important;
        }

        .categoria-sub {
            font-size: 12px !important;
        }

        .stButton > button {
            min-height: 38px !important;
            padding: 0.35rem 0.45rem !important;
            font-size: 14px !important;
        }

        .wa-alert-title {
            font-size: 18px !important;
        }

        .wa-alert-text {
            font-size: 14px !important;
        }

        .wa-alert a {
            font-size: 18px !important;
            padding: 14px 18px !important;
        }
    }

    /* ===== Ñam Ñam ordenado FINAL ===== */

    .cat-name {
        color: #FFF7E6 !important;
        font-size: 14px !important;
        font-weight: 950 !important;
        line-height: 1.1 !important;
        padding-top: 4px !important;
    }

    .cat-sub {
        color: #FFF7E6 !important;
        font-size: 10px !important;
        font-weight: 750 !important;
        opacity: .9 !important;
        line-height: 1.05 !important;
    }

    .item-name {
        color: #FFF7E6 !important;
        font-size: 14px !important;
        font-weight: 950 !important;
        line-height: 1.1 !important;
        margin-bottom: 1px !important;
    }

    .item-sub {
        color: #FFF7E6 !important;
        font-size: 11px !important;
        font-weight: 750 !important;
        opacity: .95 !important;
        line-height: 1.05 !important;
        margin-bottom: 5px !important;
    }

    div[data-testid="stNumberInput"] {
        width: 54px !important;
        min-width: 54px !important;
        max-width: 54px !important;
    }

    div[data-testid="stNumberInput"] button {
        display: none !important;
    }

    input[type="number"] {
        width: 54px !important;
        min-width: 54px !important;
        max-width: 54px !important;
        height: 31px !important;
        min-height: 31px !important;
        font-size: 13px !important;
        font-weight: 950 !important;
        text-align: center !important;
        padding: 0 !important;
        border-radius: 9px !important;
    }

    div[data-testid="column"] .stButton > button {
        min-width: 34px !important;
        width: 34px !important;
        max-width: 34px !important;
        min-height: 31px !important;
        height: 31px !important;
        padding: 0 !important;
        font-size: 13px !important;
        border-radius: 9px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        color: #111111 !important;
    }

    /* Fila de controles: - cantidad + tachito, compacta */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]) {
        width: 190px !important;
        max-width: 190px !important;
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 4px !important;
        align-items: center !important;
        justify-content: flex-start !important;
    }

    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]) > div[data-testid="column"] {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: 0 !important;
    }

    /* Categorías: nombre a la izquierda, botón VER chico a la derecha */
    .cat-row div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 8px !important;
    }

    .cat-row div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
        flex: 1 1 auto !important;
        min-width: 0 !important;
    }

    .cat-row div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
        flex: 0 0 52px !important;
        width: 52px !important;
        min-width: 52px !important;
    }

    .cat-row div[data-testid="column"] .stButton > button {
        width: 52px !important;
        min-width: 52px !important;
        max-width: 52px !important;
        height: 31px !important;
        min-height: 31px !important;
        font-size: 11px !important;
        border-radius: 9px !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        padding-top: 0.35rem !important;
        padding-bottom: 0.35rem !important;
    }

    @media (max-width: 650px) {
        .main .block-container {
            padding-left: 0.45rem !important;
            padding-right: 0.45rem !important;
        }

        .item-name {
            font-size: 13px !important;
        }

        .item-sub {
            font-size: 10px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)



def _mostrar_confirmacion_final():
    resumen = st.session_state.get("pedido_online_resumen") or {}
    wa_url = st.session_state.get("pedido_online_wa_url") or ""

    pedido_id = resumen.get("pedido_id")
    total = resumen.get("total", 0)

    st.markdown(
        f"""
        <div class="wa-alert">
            <div class="wa-alert-title">✅ Pedido #{pedido_id} registrado</div>
            <div class="wa-alert-text">
                Total: {money(total)}<br>
                Para confirmar, presioná WhatsApp.
            </div>
            <a href="{wa_url}" target="_blank">WHATSAPP</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 🧾 Resumen")
    items_resumen = resumen.get("items") or []
    if items_resumen:
        st.dataframe(
            pd.DataFrame([
                {
                    "Producto": i.get("producto_nombre"),
                    "Cant.": i.get("cantidad"),
                    "Subtotal": money(i.get("subtotal")),
                }
                for i in items_resumen
            ]),
            use_container_width=True,
            hide_index=True,
        )

    if st.button("🛒 Hacer otro pedido", use_container_width=True):
        _limpiar_carrito()
        st.rerun()


def render():
    _css()
    _init_cart()

    db = require_db()

    whatsapp_negocio = _get_config(db, "whatsapp_pedidos", WHATSAPP_NEGOCIO_DEFAULT)
    horario_reparto = _get_config(db, "horario_reparto", HORARIO_REPARTO_DEFAULT)
    puntos_retiro = _leer_locales_retiro(db)

    st.title("🍝 Ñam Ñam")
    st.caption("Pastas, pizzas, tartas y congelados")

    if st.session_state.get("pedido_online_confirmado"):
        _mostrar_confirmacion_final()
        return

    try:
        productos = [p for p in fetch_table("productos", "id") if p.get("activo")]
    except Exception as e:
        st.error("No pude leer productos.")
        st.exception(e)
        return

    promos = _leer_promos(db)

    items = _armar_items(productos, promos)
    total = sum(_float(i.get("subtotal")) for i in items)
    unidades = sum(_float(i.get("cantidad")) for i in items)

    opciones_nav = ["Categorías", "Promos", f"Carrito ({unidades:g})"]
    actual_nav = st.session_state.get("catalogo_seccion", "Categorías")

    if actual_nav.startswith("Carrito"):
        actual_index = 2
    elif actual_nav == "Promos":
        actual_index = 1
    else:
        actual_index = 0

    nav = st.radio(
        "Sección",
        opciones_nav,
        index=actual_index,
        horizontal=True,
        label_visibility="collapsed",
    )

    if nav.startswith("Carrito"):
        st.session_state["catalogo_seccion"] = "Carrito"
    else:
        st.session_state["catalogo_seccion"] = nav

    if st.session_state["catalogo_seccion"] == "Categorías":
        if not productos:
            st.info("Todavía no hay productos disponibles.")
        else:
            familias = {}
            for p in productos:
                familias.setdefault(_familia_producto(p), []).append(p)

            familias_ordenadas = _ordenar_familias(familias)

            if "cliente_categoria_abierta" not in st.session_state:
                st.session_state["cliente_categoria_abierta"] = None

            categoria_abierta = st.session_state.get("cliente_categoria_abierta")

            if categoria_abierta is None:
                st.markdown("## ¿Qué querés pedir?")

                for familia in familias_ordenadas:
                    productos_familia = familias[familia]
                    cantidad_familia = sum(_get_qty("producto", p["id"]) for p in productos_familia)
                    subtotal_familia = sum(
                        _get_qty("producto", p["id"]) * _float(p.get("precio_venta"))
                        for p in productos_familia
                    )

                    with st.container(border=True):
                        if cantidad_familia > 0:
                            sub_txt = f"{cantidad_familia:g} agregados · {money(subtotal_familia)}"
                        else:
                            sub_txt = f"{len(productos_familia)} opciones"

                        st.markdown('<div class="cat-row">', unsafe_allow_html=True)
                        c_info, c_ver = st.columns([5, 1])

                        c_info.markdown(
                            f"""
                            <div class="cat-name">{_emoji_familia(familia)} {familia}</div>
                            <div class="cat-sub">{sub_txt}</div>
                            """,
                            unsafe_allow_html=True,
                        )

                        if c_ver.button("VER", key=f"ver_familia_{familia}"):
                            st.session_state["cliente_categoria_abierta"] = familia
                            st.session_state["catalogo_seccion"] = "Categorías"
                            st.rerun()

                        st.markdown('</div>', unsafe_allow_html=True)

                st.info("Entrá a una categoría para ver sus productos.")

            else:
                st.markdown(f"## {_emoji_familia(categoria_abierta)} {categoria_abierta}")

                if st.button("⬅️ Volver a categorías"):
                    st.session_state["cliente_categoria_abierta"] = None
                    st.rerun()

                st.divider()

                for p in familias.get(categoria_abierta, []):
                    with st.container(border=True):
                        qty = int(_get_qty("producto", p["id"]))

                        st.markdown(
                            f"""
                            <div class="item-name">{p.get('nombre')}</div>
                            <div class="item-sub">{p.get('unidad') or 'unidad'} · {money(p.get('precio_venta'))}</div>
                            """,
                            unsafe_allow_html=True,
                        )

                        c_menos, c_qty, c_mas, c_borrar = st.columns([1, 1, 1, 1])

                        c_menos.button("−", key=f"menos_prod_{p['id']}", on_click=_change_qty, args=("producto", p["id"], -1))

                        key_qty = f"qty_prod_{p['id']}"
                        c_qty.number_input(
                            "Cantidad",
                            min_value=0,
                            step=1,
                            value=qty,
                            key=key_qty,
                            label_visibility="collapsed",
                            on_change=_set_qty_from_input,
                            args=("producto", p["id"], key_qty),
                        )

                        c_mas.button("➕", key=f"mas_prod_{p['id']}", on_click=_change_qty, args=("producto", p["id"], 1))

                        c_borrar.button("🗑️", key=f"borrar_prod_{p['id']}", on_click=_remove_qty, args=("producto", p["id"]))

                cantidad_categoria = sum(
                    _get_qty("producto", p["id"])
                    for p in familias.get(categoria_abierta, [])
                )
                subtotal_categoria = sum(
                    _get_qty("producto", p["id"]) * _float(p.get("precio_venta"))
                    for p in familias.get(categoria_abierta, [])
                )

                if cantidad_categoria > 0:
                    st.success(
                        f"En {categoria_abierta}: {cantidad_categoria:g} unidades · {money(subtotal_categoria)}"
                    )

    elif st.session_state["catalogo_seccion"] == "Promos":
        if not promos:
            st.info("Todavía no hay promociones disponibles.")
        else:
            for promo in promos:
                with st.container(border=True):
                    qty = int(_get_qty("promo", promo["id"]))

                    st.markdown(
                        f"""
                        <div class="item-name">🏷️ {promo.get('nombre')}</div>
                        <div class="item-sub">{money(promo.get('precio'))}</div>
                        """,
                        unsafe_allow_html=True,
                    )

                    c_menos, c_qty, c_mas, c_borrar = st.columns([1, 1, 1, 1])

                    c_menos.button("−", key=f"menos_promo_{promo['id']}", on_click=_change_qty, args=("promo", promo["id"], -1))

                    key_qty = f"qty_promo_{promo['id']}"
                    c_qty.number_input(
                        "Cantidad",
                        min_value=0,
                        step=1,
                        value=qty,
                        key=key_qty,
                        label_visibility="collapsed",
                        on_change=_set_qty_from_input,
                        args=("promo", promo["id"], key_qty),
                    )

                    c_mas.button("➕", key=f"mas_promo_{promo['id']}", on_click=_change_qty, args=("promo", promo["id"], 1))

                    c_borrar.button("🗑️", key=f"borrar_promo_{promo['id']}", on_click=_remove_qty, args=("promo", promo["id"]))

                    detalles = _leer_detalle_promo(db, promo["id"])
                    if detalles:
                        with st.expander("Ver productos incluidos"):
                            st.dataframe(
                                pd.DataFrame([
                                    {
                                        "Producto": d.get("producto_nombre"),
                                        "Cantidad": d.get("cantidad"),
                                    }
                                    for d in detalles
                                ]),
                                use_container_width=True,
                                hide_index=True
                            )

    elif st.session_state["catalogo_seccion"] == "Carrito":
        st.subheader("🛒 Tu pedido")

        if not items:
            st.info("Todavía no agregaste productos.")
        else:
            st.caption("Podés tocar el número y escribir la cantidad.")

            for it in items:
                tipo_item = it.get("tipo")
                item_id = it.get("promo_id") if tipo_item == "promo" else it.get("producto_id")
                nombre_item = it.get("producto_nombre")
                precio_unitario = _float(it.get("precio_unitario"))
                cantidad_item = int(_float(it.get("cantidad")))
                subtotal_item = _float(it.get("subtotal"))

                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div class="item-name">{nombre_item}</div>
                        <div class="item-sub">{money(precio_unitario)} c/u · Subtotal: {money(subtotal_item)}</div>
                        """,
                        unsafe_allow_html=True,
                    )

                    c_menos, c_qty, c_mas, c_borrar = st.columns([1, 1, 1, 1])

                    c_menos.button(
                        "−",
                        key=f"cart_menos_{tipo_item}_{item_id}",
                        on_click=lambda t=tipo_item, i=item_id: (_set_seccion("Carrito"), _change_qty(t, i, -1)),
                    )

                    key_qty = f"cart_qty_{tipo_item}_{item_id}"
                    c_qty.number_input(
                        "Cantidad",
                        min_value=0,
                        step=1,
                        value=cantidad_item,
                        key=key_qty,
                        label_visibility="collapsed",
                        on_change=lambda t=tipo_item, i=item_id, k=key_qty: (_set_seccion("Carrito"), _set_qty_from_input(t, i, k)),
                    )

                    c_mas.button(
                        "➕",
                        key=f"cart_mas_{tipo_item}_{item_id}",
                        on_click=lambda t=tipo_item, i=item_id: (_set_seccion("Carrito"), _change_qty(t, i, 1)),
                    )

                    c_borrar.button(
                        "🗑️",
                        key=f"cart_borrar_{tipo_item}_{item_id}",
                        on_click=lambda t=tipo_item, i=item_id: (_set_seccion("Carrito"), _remove_qty(t, i)),
                    )

            st.markdown(f"## Total: {money(total)}")

        st.divider()
        st.subheader("👤 Datos del pedido")

        c1, c2 = st.columns(2)

        with c1:
            nombre = st.text_input("Nombre y apellido *")
            telefono = st.text_input("Teléfono / WhatsApp *")

        with c2:
            forma_pago = st.radio("Forma de pago", ["Efectivo", "Transferencia"], horizontal=True)

        st.divider()
        st.subheader("🚚 Entrega")

        tipo_entrega = st.radio("¿Cómo querés recibir el pedido?", ["Retira en local", "Envío a domicilio"], horizontal=True)

        punto_retiro = None
        direccion = ""
        barrio = ""
        referencia = ""

        if tipo_entrega == "Retira en local":
            punto_retiro = st.selectbox("¿Dónde querés retirar?", list(puntos_retiro.keys()))
            info = puntos_retiro[punto_retiro]
            st.info(f"📍 {info['direccion']}\n\n🕒 {info['horarios']}")
        else:
            st.info(horario_reparto)
            direccion = st.text_input("Dirección *")
            barrio = st.text_input("Barrio")
            referencia = st.text_input("Referencia", placeholder="Ej: portón negro, casa verde, tocar timbre")

        programar = st.radio("Horario", ["Lo antes posible", "Programar fecha y hora"], horizontal=True)

        fecha_entrega = None
        hora_entrega = None

        if programar == "Programar fecha y hora":
            cfecha, chora = st.columns(2)
            fecha_entrega = cfecha.date_input("Fecha")
            hora_entrega = chora.time_input("Hora")

        observaciones = st.text_area("Observaciones", placeholder="Ej: sin cebolla, llamar al llegar, etc.")

        confirmar = st.button("✅ Confirmar pedido", use_container_width=True)

        if st.button("🗑️ Limpiar carrito", use_container_width=True):
            _limpiar_carrito()
            st.session_state["catalogo_seccion"] = "Carrito"
            st.rerun()

        if confirmar:
            if not items:
                st.warning("Agregá al menos un producto o una promo.")
                return

            if not nombre.strip() or not telefono.strip():
                st.warning("Completá nombre y teléfono.")
                return

            if tipo_entrega == "Envío a domicilio" and not direccion.strip():
                st.warning("Completá la dirección de entrega.")
                return

            tipo_cobro = "Pendiente"
            pagado = False

            pedido = db.table(table("pedidos")).insert({
                "cliente_id": None,
                "cliente_nombre": nombre.strip(),
                "telefono_cliente": telefono.strip(),
                "estado": "Pendiente",
                "total": total,
                "observaciones": observaciones.strip(),
                "pagado": pagado,
                "forma_pago": forma_pago,
                "tipo_cobro": tipo_cobro,
                "tipo_entrega": tipo_entrega,
                "punto_retiro": punto_retiro,
                "direccion_entrega": direccion.strip(),
                "barrio_entrega": barrio.strip(),
                "referencia_entrega": referencia.strip(),
                "fecha_entrega": fecha_entrega.isoformat() if fecha_entrega else None,
                "hora_entrega": hora_entrega.isoformat() if hora_entrega else None,
            }).execute().data[0]

            for it in items:
                it["pedido_id"] = pedido["id"]

            db.table(table("pedido_detalles")).insert(items).execute()

            mensaje = _mensaje_whatsapp(
                pedido["id"],
                nombre.strip(),
                telefono.strip(),
                tipo_entrega,
                punto_retiro,
                direccion.strip(),
                barrio.strip(),
                referencia.strip(),
                fecha_entrega.isoformat() if fecha_entrega else None,
                hora_entrega.isoformat() if hora_entrega else None,
                forma_pago,
                items,
                total,
            )

            url = (
                f"https://api.whatsapp.com/send?"
                f"phone={whatsapp_negocio}"
                f"&text={urllib.parse.quote(mensaje)}"
            )

            st.session_state["pedido_online_confirmado"] = True
            st.session_state["pedido_online_wa_url"] = url
            st.session_state["pedido_online_resumen"] = {
                "pedido_id": pedido["id"],
                "nombre": nombre.strip(),
                "telefono": telefono.strip(),
                "forma_pago": forma_pago,
                "tipo_entrega": tipo_entrega,
                "punto_retiro": punto_retiro,
                "direccion": direccion.strip(),
                "barrio": barrio.strip(),
                "referencia": referencia.strip(),
                "fecha": fecha_entrega.isoformat() if fecha_entrega else None,
                "hora": hora_entrega.isoformat() if hora_entrega else None,
                "items": items,
                "total": total,
            }

            # Vacío el carrito interno para evitar duplicados,
            # pero conservo el resumen confirmado en pantalla.
            st.session_state["cliente_productos"] = {}
            st.session_state["cliente_promos"] = {}

            st.rerun()