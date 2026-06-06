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
    </style>
    """, unsafe_allow_html=True)



def _mostrar_confirmacion_final():
    resumen = st.session_state.get("pedido_online_resumen") or {}
    wa_url = st.session_state.get("pedido_online_wa_url") or ""

    st.markdown(
        f"""
        <div class="wa-alert">
            <div class="wa-alert-title">✅ Pedido registrado correctamente</div>
            <div class="wa-alert-text">
                Para confirmar el pedido, presioná el botón de WhatsApp.
            </div>
            <a href="{wa_url}" target="_blank">WHATSAPP</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown("## 🧾 Resumen del pedido")

    pedido_id = resumen.get("pedido_id")
    if pedido_id:
        st.markdown(f"### Pedido #{pedido_id}")

    datos = [
        {"Dato": "Cliente", "Valor": resumen.get("nombre", "")},
        {"Dato": "Teléfono", "Valor": resumen.get("telefono", "")},
        {"Dato": "Forma de pago", "Valor": resumen.get("forma_pago", "")},
        {"Dato": "Entrega", "Valor": resumen.get("tipo_entrega", "")},
    ]

    if resumen.get("tipo_entrega") == "Retira en local":
        datos.append({"Dato": "Retira en", "Valor": resumen.get("punto_retiro", "")})
    else:
        datos.append({"Dato": "Dirección", "Valor": resumen.get("direccion", "")})
        if resumen.get("barrio"):
            datos.append({"Dato": "Barrio", "Valor": resumen.get("barrio", "")})
        if resumen.get("referencia"):
            datos.append({"Dato": "Referencia", "Valor": resumen.get("referencia", "")})

    datos.append({"Dato": "Fecha", "Valor": resumen.get("fecha") or "A coordinar"})
    datos.append({"Dato": "Hora", "Valor": resumen.get("hora") or "A coordinar"})

    st.dataframe(pd.DataFrame(datos), use_container_width=True, hide_index=True)

    items_resumen = resumen.get("items") or []
    if items_resumen:
        st.markdown("### Productos")
        st.dataframe(
            pd.DataFrame([
                {
                    "Producto": i.get("producto_nombre"),
                    "Cantidad": i.get("cantidad"),
                    "Subtotal": money(i.get("subtotal")),
                }
                for i in items_resumen
            ]),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(f"## Total: {money(resumen.get('total', 0))}")

    if st.button("Hacer otro pedido"):
        _limpiar_carrito()
        st.rerun()


def render():
    _css()
    _init_cart()

    db = require_db()

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

    tab_productos, tab_promos, tab_carrito = st.tabs(["📂 Categorías", "🏷️ Promos", f"🛒 Carrito ({unidades:g})"])

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
                        c1, c2 = st.columns([4, 1])

                        c1.markdown(f"### {_emoji_familia(familia)} {familia}")
                        if cantidad_familia > 0:
                            c1.caption(f"{cantidad_familia:g} productos agregados · {money(subtotal_familia)}")
                        else:
                            c1.caption(f"{len(productos_familia)} opciones disponibles")

                        if c2.button("Ver", key=f"ver_familia_{familia}"):
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

            url = (
                f"https://api.whatsapp.com/send?"
                f"phone={WHATSAPP_NEGOCIO}"
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
