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
    if "cliente_promos_flex" not in st.session_state:
        st.session_state["cliente_promos_flex"] = {}
    st.session_state["cliente_promos_combo"] = {}
    if "cliente_promos_combo" not in st.session_state:
        st.session_state["cliente_promos_combo"] = {}
    if "pedido_online_confirmado" not in st.session_state:
        st.session_state["pedido_online_confirmado"] = False
    if "pedido_online_wa_url" not in st.session_state:
        st.session_state["pedido_online_wa_url"] = ""
    if "pedido_online_resumen" not in st.session_state:
        st.session_state["pedido_online_resumen"] = None


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


def _limpiar_carrito():
    st.session_state["cliente_productos"] = {}
    st.session_state["cliente_promos"] = {}
    st.session_state["cliente_promos_flex"] = {}
    st.session_state["cliente_promos_combo"] = {}
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


def _leer_promos_flexibles(db):
    try:
        return (
            db.table("namnam_promos_flexibles")
            .select("*")
            .eq("activo", True)
            .order("id")
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _familia_producto_valor(p):
    return str(
        p.get("familia")
        or p.get("categoria")
        or p.get("categoría")
        or p.get("rubro")
        or p.get("grupo")
        or "Otros"
    ).strip()


def _productos_para_promo_flexible(productos, promo):
    familia = str(promo.get("familia_incluida") or "").strip().lower()
    excluir = str(promo.get("texto_excluir") or "").strip().lower()
    res = []

    for p in productos:
        fam = _familia_producto_valor(p).lower()
        nombre = str(p.get("nombre") or "").lower()

        if familia and fam != familia:
            continue

        if excluir and (excluir in fam or excluir in nombre):
            continue

        res.append(p)

    return res


def _flex_key(promo_id, producto_id):
    return f"{promo_id}:{producto_id}"


def _get_flex_qty(promo_id, producto_id):
    if "cliente_promos_flex" not in st.session_state:
        st.session_state["cliente_promos_flex"] = {}
    st.session_state["cliente_promos_combo"] = {}
    if "cliente_promos_combo" not in st.session_state:
        st.session_state["cliente_promos_combo"] = {}
    return _float(st.session_state["cliente_promos_flex"].get(_flex_key(promo_id, producto_id), 0))


def _set_flex_qty(promo_id, producto_id, value):
    if "cliente_promos_flex" not in st.session_state:
        st.session_state["cliente_promos_flex"] = {}
    st.session_state["cliente_promos_combo"] = {}
    if "cliente_promos_combo" not in st.session_state:
        st.session_state["cliente_promos_combo"] = {}

    key = _flex_key(promo_id, producto_id)
    value = _float(value)

    if value <= 0:
        st.session_state["cliente_promos_flex"].pop(key, None)
    else:
        st.session_state["cliente_promos_flex"][key] = value


def _change_flex_qty(promo_id, producto_id, delta):
    actual = _get_flex_qty(promo_id, producto_id)
    _set_flex_qty(promo_id, producto_id, max(0, actual + delta))


def _set_flex_qty_from_input(promo_id, producto_id, key):
    _set_flex_qty(promo_id, producto_id, st.session_state.get(key, 0))


def _flex_total_seleccionado(promo_id):
    if "cliente_promos_flex" not in st.session_state:
        st.session_state["cliente_promos_flex"] = {}
    st.session_state["cliente_promos_combo"] = {}
    if "cliente_promos_combo" not in st.session_state:
        st.session_state["cliente_promos_combo"] = {}

    prefix = f"{promo_id}:"
    return sum(
        _float(v)
        for k, v in st.session_state["cliente_promos_flex"].items()
        if str(k).startswith(prefix)
    )


def _armar_items_flexibles(productos, promos_flexibles):
    items = []

    for promo in promos_flexibles:
        promo_id = promo["id"]
        requerido = _float(promo.get("cantidad_requerida"))
        seleccionado = _flex_total_seleccionado(promo_id)

        if seleccionado <= 0 or seleccionado != requerido:
            continue

        detalle = []
        for p in _productos_para_promo_flexible(productos, promo):
            cant = _get_flex_qty(promo_id, p["id"])
            if cant > 0:
                detalle.append({
                    "producto_id": p["id"],
                    "producto_nombre": p.get("nombre"),
                    "cantidad": cant,
                })

        precio = _float(promo.get("precio"))

        items.append({
            "tipo": "promo_flexible",
            "producto_id": None,
            "producto_nombre": promo.get("nombre"),
            "cantidad": 1,
            "precio_unitario": precio,
            "subtotal": precio,
            "promo_id": None,
            "promo_flexible_id": promo_id,
            "promo_flexible_nombre": promo.get("nombre"),
            "detalle_flexible": detalle,
        })

    return items


def _leer_promos_combinadas(db):
    try:
        return db.table("namnam_promos_combinadas").select("*").eq("activo", True).order("id").execute().data or []
    except Exception:
        return []


def _leer_grupos_promo_combinada(db, promo_id):
    try:
        return db.table("namnam_promos_combinadas_grupos").select("*").eq("promo_id", promo_id).order("orden").execute().data or []
    except Exception:
        return []


def _combo_key(promo_id, grupo_id, producto_id):
    return f"{promo_id}:{grupo_id}:{producto_id}"


def _get_combo_qty(promo_id, grupo_id, producto_id):
    if "cliente_promos_combo" not in st.session_state:
        st.session_state["cliente_promos_combo"] = {}
    return _float(st.session_state["cliente_promos_combo"].get(_combo_key(promo_id, grupo_id, producto_id), 0))


def _set_combo_qty(promo_id, grupo_id, producto_id, value):
    if "cliente_promos_combo" not in st.session_state:
        st.session_state["cliente_promos_combo"] = {}
    key = _combo_key(promo_id, grupo_id, producto_id)
    value = _float(value)
    if value <= 0:
        st.session_state["cliente_promos_combo"].pop(key, None)
    else:
        st.session_state["cliente_promos_combo"][key] = value


def _change_combo_qty(promo_id, grupo_id, producto_id, delta):
    actual = _get_combo_qty(promo_id, grupo_id, producto_id)
    _set_combo_qty(promo_id, grupo_id, producto_id, max(0, actual + delta))


def _set_combo_qty_from_input(promo_id, grupo_id, producto_id, key):
    _set_combo_qty(promo_id, grupo_id, producto_id, st.session_state.get(key, 0))


def _combo_total_grupo(promo_id, grupo_id):
    if "cliente_promos_combo" not in st.session_state:
        st.session_state["cliente_promos_combo"] = {}
    prefix = f"{promo_id}:{grupo_id}:"
    return sum(_float(v) for k, v in st.session_state["cliente_promos_combo"].items() if str(k).startswith(prefix))


def _productos_para_grupo_combinado(productos, grupo):
    familia = str(grupo.get("familia") or "").strip().lower()
    excluir = str(grupo.get("texto_excluir") or "").strip().lower()
    res = []
    for p in productos:
        fam = _familia_producto_valor(p).lower()
        nombre = str(p.get("nombre") or "").lower()
        if familia and fam != familia:
            continue
        if excluir and (excluir in fam or excluir in nombre):
            continue
        res.append(p)
    return res


def _armar_items_combinados(productos, promos_combinadas, grupos_por_promo):
    items = []
    for promo in promos_combinadas:
        promo_id = promo["id"]
        grupos = grupos_por_promo.get(promo_id, [])
        if not grupos:
            continue
        completa = True
        detalle = []
        for grupo in grupos:
            grupo_id = grupo["id"]
            requerido = _float(grupo.get("cantidad_requerida"))
            seleccionado = _combo_total_grupo(promo_id, grupo_id)
            if seleccionado != requerido:
                completa = False
                break
            for p in _productos_para_grupo_combinado(productos, grupo):
                cant = _get_combo_qty(promo_id, grupo_id, p["id"])
                if cant > 0:
                    detalle.append({"grupo_id": grupo_id, "familia": grupo.get("familia"), "producto_id": p["id"], "producto_nombre": p.get("nombre"), "cantidad": cant})
        if not completa:
            continue
        precio = _float(promo.get("precio"))
        items.append({"tipo": "promo_combinada", "producto_id": None, "producto_nombre": promo.get("nombre"), "cantidad": 1, "precio_unitario": precio, "subtotal": precio, "promo_id": None, "promo_combinada_id": promo_id, "promo_combinada_nombre": promo.get("nombre"), "detalle_combinada": detalle})
    return items


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

        if it.get("detalle_flexible"):
            for det in it.get("detalle_flexible") or []:
                lineas.append(f"  • {det['cantidad']:g} x {det['producto_nombre']}")

        if it.get("detalle_combinada"):
            for det in it.get("detalle_combinada") or []:
                lineas.append(f"  • {det['familia']}: {det['cantidad']:g} x {det['producto_nombre']}")

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
    promos_flexibles = _leer_promos_flexibles(db)
    promos_combinadas = _leer_promos_combinadas(db)
    grupos_combinadas = {promo["id"]: _leer_grupos_promo_combinada(db, promo["id"]) for promo in promos_combinadas}

    items = (_armar_items(productos, promos) + _armar_items_flexibles(productos, promos_flexibles) + _armar_items_combinados(productos, promos_combinadas, grupos_combinadas))
    total = sum(_float(i.get("subtotal")) for i in items)
    unidades = sum(_float(i.get("cantidad")) for i in items)

    tab_productos, tab_promos, tab_promos_flex, tab_promos_combo, tab_carrito = st.tabs(["📂 Categorías", "🏷️ Promos", "🧺 Flexibles", "🧩 Combinadas", f"🛒 Carrito ({unidades:g})"])

    with tab_productos:
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
                        st.markdown(
                            f"""
                            <div class="categoria-card">{_emoji_familia(familia)} {familia}</div>
                            """,
                            unsafe_allow_html=True,
                        )

                        if cantidad_familia > 0:
                            st.markdown(
                                f"""<div class="categoria-sub">{cantidad_familia:g} productos agregados · {money(subtotal_familia)}</div>""",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f"""<div class="categoria-sub">{len(productos_familia)} opciones disponibles</div>""",
                                unsafe_allow_html=True,
                            )

                        if st.button("Ver productos", key=f"ver_familia_{familia}", use_container_width=True):
                            st.session_state["cliente_categoria_abierta"] = familia
                            st.rerun()

                st.info("Entrá a una categoría para ver sus productos.")

            else:
                st.markdown(f"## {_emoji_familia(categoria_abierta)} {categoria_abierta}")

                if st.button("⬅️ Volver a categorías"):
                    st.session_state["cliente_categoria_abierta"] = None
                    st.rerun()

                st.divider()

                for p in familias.get(categoria_abierta, []):
                    with st.container(border=True):
                        st.markdown(
                            f"""
                            <div class="producto-nombre">{p.get('nombre')}</div>
                            <div class="producto-info">{p.get('unidad') or 'unidad'} · {money(p.get('precio_venta'))}</div>
                            """,
                            unsafe_allow_html=True,
                        )

                        qty = _get_qty("producto", p["id"])
                        c_menos, c_qty, c_mas = st.columns([1, 1, 1])

                        if c_menos.button("➖", key=f"menos_prod_{p['id']}", use_container_width=True):
                            _change_qty("producto", p["id"], -1)
                            st.rerun()

                        c_qty.markdown(f"""<div class="qty-num">{qty:g}</div>""", unsafe_allow_html=True)

                        if c_mas.button("➕", key=f"mas_prod_{p['id']}", use_container_width=True):
                            _change_qty("producto", p["id"], 1)
                            st.rerun()

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

    with tab_promos:
        if not promos:
            st.info("Todavía no hay promociones disponibles.")
        else:
            for promo in promos:
                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div class="producto-nombre">🏷️ {promo.get('nombre')}</div>
                        <div class="producto-info">{promo.get('descripcion') or ''}</div>
                        <div class="producto-info"><strong>{money(promo.get('precio'))}</strong></div>
                        """,
                        unsafe_allow_html=True,
                    )

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

                    qty = _get_qty("promo", promo["id"])
                    c_menos, c_qty, c_mas = st.columns([1, 1, 1])

                    if c_menos.button("➖", key=f"menos_promo_{promo['id']}", use_container_width=True):
                        _change_qty("promo", promo["id"], -1)
                        st.rerun()

                    c_qty.markdown(f"""<div class="qty-num">{qty:g}</div>""", unsafe_allow_html=True)

                    if c_mas.button("➕", key=f"mas_promo_{promo['id']}", use_container_width=True):
                        _change_qty("promo", promo["id"], 1)
                        st.rerun()


    with tab_promos_flex:
        if not promos_flexibles:
            st.info("Todavía no hay promociones flexibles disponibles.")
        else:
            for promo_flex in promos_flexibles:
                with st.container(border=True):
                    promo_id = promo_flex["id"]
                    requerido = _float(promo_flex.get("cantidad_requerida"))
                    seleccionado = _flex_total_seleccionado(promo_id)
                    faltan = max(0, requerido - seleccionado)

                    st.markdown(f"### 🧺 {promo_flex.get('nombre')}")
                    if promo_flex.get("descripcion"):
                        st.caption(promo_flex.get("descripcion"))

                    st.write(f"Elegidas: **{seleccionado:g} / {requerido:g}**")
                    st.write(f"Precio promo: **{money(promo_flex.get('precio'))}**")

                    if faltan > 0:
                        st.warning(f"Faltan elegir {faltan:g}.")
                    elif seleccionado > requerido:
                        st.error(f"Te pasaste por {seleccionado - requerido:g}. Bajá cantidades.")
                    else:
                        st.success("Promo completa. Se agregará al carrito.")

                    productos_flex = _productos_para_promo_flexible(productos, promo_flex)

                    with st.expander("Elegir productos de la promo", expanded=True):
                        if not productos_flex:
                            st.info("No hay productos disponibles para esta promo.")
                        else:
                            for p in productos_flex:
                                qty = int(_get_flex_qty(promo_id, p["id"]))

                                st.markdown(
                                    f"""
                                    <div class="producto-nombre">{p.get('nombre')}</div>
                                    <div class="producto-info">{p.get('unidad') or 'unidad'} · incluido en promo</div>
                                    """,
                                    unsafe_allow_html=True,
                                )

                                c_menos, c_qty, c_mas, c_borrar = st.columns([1, 1, 1, 1])

                                c_menos.button(
                                    "−",
                                    key=f"flex_menos_{promo_id}_{p['id']}",
                                    on_click=_change_flex_qty,
                                    args=(promo_id, p["id"], -1),
                                )

                                key_qty = f"flex_qty_{promo_id}_{p['id']}"
                                c_qty.number_input(
                                    "Cantidad",
                                    min_value=0,
                                    step=1,
                                    value=qty,
                                    key=key_qty,
                                    label_visibility="collapsed",
                                    on_change=_set_flex_qty_from_input,
                                    args=(promo_id, p["id"], key_qty),
                                )

                                c_mas.button(
                                    "➕",
                                    key=f"flex_mas_{promo_id}_{p['id']}",
                                    on_click=_change_flex_qty,
                                    args=(promo_id, p["id"], 1),
                                )

                                c_borrar.button(
                                    "🗑️",
                                    key=f"flex_borrar_{promo_id}_{p['id']}",
                                    on_click=_set_flex_qty,
                                    args=(promo_id, p["id"], 0),
                                )


    with tab_promos_combo:
        if not promos_combinadas:
            st.info("Todavía no hay promociones combinadas disponibles.")
        else:
            for promo_combo in promos_combinadas:
                promo_id = promo_combo["id"]
                grupos = grupos_combinadas.get(promo_id, [])
                with st.container(border=True):
                    st.markdown(f"### 🧩 {promo_combo.get('nombre')}")
                    if promo_combo.get("descripcion"):
                        st.caption(promo_combo.get("descripcion"))
                    st.write(f"Precio promo: **{money(promo_combo.get('precio'))}**")
                    completa = True
                    for grupo in grupos:
                        grupo_id = grupo["id"]
                        requerido = _float(grupo.get("cantidad_requerida"))
                        seleccionado = _combo_total_grupo(promo_id, grupo_id)
                        if seleccionado != requerido:
                            completa = False
                        titulo_grupo = f"{grupo.get('familia')} — {seleccionado:g} / {requerido:g}"
                        with st.expander(titulo_grupo, expanded=True):
                            if seleccionado < requerido:
                                st.warning(f"Faltan elegir {requerido - seleccionado:g}.")
                            elif seleccionado > requerido:
                                st.error(f"Te pasaste por {seleccionado - requerido:g}. Bajá cantidades.")
                            else:
                                st.success("Grupo completo.")
                            productos_grupo = _productos_para_grupo_combinado(productos, grupo)
                            if not productos_grupo:
                                st.info("No hay productos disponibles para este grupo.")
                            else:
                                for p in productos_grupo:
                                    qty = int(_get_combo_qty(promo_id, grupo_id, p["id"]))
                                    total_grupo = _combo_total_grupo(promo_id, grupo_id)
                                    deshabilitar_sumar = total_grupo >= requerido and qty <= 0
                                    max_manual = int(qty + max(0, requerido - total_grupo))
                                    st.markdown(f"""
                                        <div class="producto-nombre">{p.get('nombre')}</div>
                                        <div class="producto-info">{p.get('unidad') or 'unidad'} · grupo {grupo.get('familia')}</div>
                                    """, unsafe_allow_html=True)
                                    c_menos, c_qty, c_mas, c_borrar = st.columns([1, 1, 1, 1])
                                    c_menos.button("−", key=f"combo_menos_{promo_id}_{grupo_id}_{p['id']}", on_click=_change_combo_qty, args=(promo_id, grupo_id, p["id"], -1))
                                    key_qty = f"combo_qty_{promo_id}_{grupo_id}_{p['id']}"
                                    c_qty.number_input("Cantidad", min_value=0, max_value=max(0, max_manual), step=1, value=qty, key=key_qty, label_visibility="collapsed", on_change=_set_combo_qty_from_input, args=(promo_id, grupo_id, p["id"], key_qty))
                                    c_mas.button("➕", key=f"combo_mas_{promo_id}_{grupo_id}_{p['id']}", on_click=_change_combo_qty, args=(promo_id, grupo_id, p["id"], 1), disabled=deshabilitar_sumar)
                                    c_borrar.button("🗑️", key=f"combo_borrar_{promo_id}_{grupo_id}_{p['id']}", on_click=_set_combo_qty, args=(promo_id, grupo_id, p["id"], 0))
                    if completa and grupos:
                        st.success("Promo combinada completa. Se agregará al carrito.")
                    else:
                        st.info("Completá todos los grupos para sumar esta promo al carrito.")

    with tab_carrito:
        st.subheader("🛒 Tu pedido")

        if not items:
            st.info("Todavía no agregaste productos.")
        else:
            st.dataframe(
                pd.DataFrame([
                    {
                        "Detalle": i.get("producto_nombre"),
                        "Cantidad": i.get("cantidad"),
                        "Precio": money(i.get("precio_unitario")),
                        "Subtotal": money(i.get("subtotal")),
                    }
                    for i in items
                ]),
                use_container_width=True,
                hide_index=True
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
            st.rerun()

        if confirmar:
            for promo_flex in promos_flexibles:
                seleccionado_flex = _flex_total_seleccionado(promo_flex["id"])
                requerido_flex = _float(promo_flex.get("cantidad_requerida"))
                if seleccionado_flex > 0 and seleccionado_flex != requerido_flex:
                    st.warning(f"La promo '{promo_flex.get('nombre')}' necesita exactamente {requerido_flex:g} unidades. Ahora tiene {seleccionado_flex:g}.")
                    return

            for promo_combo in promos_combinadas:
                promo_id_combo = promo_combo["id"]
                for grupo_combo in grupos_combinadas.get(promo_id_combo, []):
                    seleccionado_combo = _combo_total_grupo(promo_id_combo, grupo_combo["id"])
                    requerido_combo = _float(grupo_combo.get("cantidad_requerida"))
                    if seleccionado_combo > 0 and seleccionado_combo != requerido_combo:
                        st.warning(f"La promo '{promo_combo.get('nombre')}' necesita exactamente {requerido_combo:g} de {grupo_combo.get('familia')}. Ahora tiene {seleccionado_combo:g}.")
                        return

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

            detalles_para_insertar = []
            flex_items_para_insertar = []
            combo_items_para_insertar = []

            for it in items:
                it_db = dict(it)
                detalle_flexible = it_db.pop("detalle_flexible", None)
                detalle_combinada = it_db.pop("detalle_combinada", None)
                detalles_para_insertar.append(it_db)

                if detalle_flexible and it.get("promo_flexible_id"):
                    for det in detalle_flexible:
                        flex_items_para_insertar.append({
                            "pedido_id": pedido["id"],
                            "promo_flexible_id": it.get("promo_flexible_id"),
                            "producto_id": det.get("producto_id"),
                            "producto_nombre": det.get("producto_nombre"),
                            "cantidad": det.get("cantidad"),
                        })

                if detalle_combinada and it.get("promo_combinada_id"):
                    for det in detalle_combinada:
                        combo_items_para_insertar.append({"pedido_id": pedido["id"], "promo_combinada_id": it.get("promo_combinada_id"), "grupo_id": det.get("grupo_id"), "familia": det.get("familia"), "producto_id": det.get("producto_id"), "producto_nombre": det.get("producto_nombre"), "cantidad": det.get("cantidad")})

            if detalles_para_insertar:
                db.table(table("pedido_detalles")).insert(detalles_para_insertar).execute()

            if flex_items_para_insertar:
                db.table("namnam_pedido_promo_flexible_items").insert(flex_items_para_insertar).execute()

            if combo_items_para_insertar:
                db.table("namnam_pedido_promo_combinada_items").insert(combo_items_para_insertar).execute()

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