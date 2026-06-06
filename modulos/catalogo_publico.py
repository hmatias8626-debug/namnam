import urllib.parse

import pandas as pd
import streamlit as st

from services.db import require_db, fetch_table, table, money


WHATSAPP_NEGOCIO = "5493812019770"

PUNTOS_RETIRO = {
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

HORARIO_REPARTO = """
Repartos disponibles según zona y disponibilidad.
El horario será confirmado por WhatsApp al recibir el pedido.
"""


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
    </style>
    """, unsafe_allow_html=True)


def render():
    _css()
    _init_cart()

    db = require_db()

    st.title("🍝 Ñam Ñam")
    st.caption("Pastas, pizzas, tartas y congelados")

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

    tab_productos, tab_promos, tab_carrito = st.tabs(["📦 Productos", "🏷️ Promos", f"🛒 Carrito ({unidades:g})"])

    with tab_productos:
        if not productos:
            st.info("Todavía no hay productos disponibles.")
        else:
            familias = {}
            for p in productos:
                familias.setdefault(_familia_producto(p), []).append(p)

            familias_ordenadas = _ordenar_familias(familias)

            if "cliente_familia" not in st.session_state:
                st.session_state["cliente_familia"] = familias_ordenadas[0]

            if st.session_state["cliente_familia"] not in familias_ordenadas:
                st.session_state["cliente_familia"] = familias_ordenadas[0]

            labels = [f"{_emoji_familia(f)} {f}" for f in familias_ordenadas]
            label_to_family = {f"{_emoji_familia(f)} {f}": f for f in familias_ordenadas}

            actual = st.session_state["cliente_familia"]
            actual_label = f"{_emoji_familia(actual)} {actual}"
            idx = labels.index(actual_label) if actual_label in labels else 0

            selected = st.radio("Categoría", labels, index=idx, horizontal=True)
            familia = label_to_family[selected]
            st.session_state["cliente_familia"] = familia

            st.markdown(f"## {_emoji_familia(familia)} {familia}")

            for p in familias[familia]:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([4, 1, 1, 1])

                    c1.markdown(f"### {p.get('nombre')}")
                    c1.caption(f"{p.get('unidad') or 'unidad'} · {money(p.get('precio_venta'))}")

                    qty = _get_qty("producto", p["id"])
                    if c2.button("➖", key=f"menos_prod_{p['id']}"):
                        _change_qty("producto", p["id"], -1)
                        st.rerun()

                    c3.markdown(f"### {qty:g}")

                    if c4.button("➕", key=f"mas_prod_{p['id']}"):
                        _change_qty("producto", p["id"], 1)
                        st.rerun()

    with tab_promos:
        if not promos:
            st.info("Todavía no hay promociones disponibles.")
        else:
            for promo in promos:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([4, 1, 1, 1])

                    c1.markdown(f"### 🏷️ {promo.get('nombre')}")
                    if promo.get("descripcion"):
                        c1.caption(promo.get("descripcion"))

                    detalles = _leer_detalle_promo(db, promo["id"])
                    if detalles:
                        with c1.expander("Ver productos incluidos"):
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

                    c1.markdown(f"**{money(promo.get('precio'))}**")

                    qty = _get_qty("promo", promo["id"])

                    if c2.button("➖", key=f"menos_promo_{promo['id']}"):
                        _change_qty("promo", promo["id"], -1)
                        st.rerun()

                    c3.markdown(f"### {qty:g}")

                    if c4.button("➕", key=f"mas_promo_{promo['id']}"):
                        _change_qty("promo", promo["id"], 1)
                        st.rerun()

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
            punto_retiro = st.selectbox("¿Dónde querés retirar?", list(PUNTOS_RETIRO.keys()))
            info = PUNTOS_RETIRO[punto_retiro]
            st.info(f"📍 {info['direccion']}\n\n🕒 {info['horarios']}")
        else:
            st.info(HORARIO_REPARTO)
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

        col_confirmar, col_limpiar = st.columns([2, 1])

        with col_limpiar:
            if st.button("Limpiar carrito"):
                _limpiar_carrito()
                st.rerun()

        with col_confirmar:
            confirmar = st.button("✅ Confirmar pedido", use_container_width=True)

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

            _limpiar_carrito()

            st.success(f"Pedido #{pedido['id']} creado correctamente.")
            url = f"https://wa.me/{WHATSAPP_NEGOCIO}?text={urllib.parse.quote(mensaje)}"
            st.link_button("📲 Enviar pedido por WhatsApp", url)
