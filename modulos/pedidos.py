import pandas as pd
import streamlit as st

from services.db import require_db, fetch_table, money, table
from services.ui import header

ESTADOS = ["Pendiente", "En preparación", "Listo", "En reparto", "Entregado"]
FORMAS_MINORISTA = ["Efectivo", "Transferencia", "Mercado Pago", "Pendiente"]
FORMAS_MAYORISTA = ["Cobrar ahora", "Usar saldo mayorista"]


def _float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _nombre_cliente(c):
    completo = f"{c.get('nombre') or ''} {c.get('apellido') or ''}".strip()
    tel = c.get("telefono") or ""
    return f"{completo} - {tel}" if tel else (completo or f"Cliente #{c.get('id')}")


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


def _precio_para_cliente(producto, cliente):
    if (cliente or {}).get("tipo_cliente") == "Mayorista":
        return _float(producto.get("precio_mayorista") or producto.get("precio_venta"))
    return _float(producto.get("precio_venta"))


def _registrar_caja(db, pedido, forma_pago):
    db.table(table("caja")).insert({
        "tipo": "Ingreso",
        "concepto": f"Cobro pedido #{pedido['id']}",
        "importe": _float(pedido.get("total")),
        "observaciones": f"Cliente: {pedido.get('cliente_nombre') or ''}",
        "pedido_id": pedido["id"],
        "cliente_id": pedido.get("cliente_id"),
        "forma_pago": forma_pago,
        "medio": forma_pago,
    }).execute()


def _usar_saldo_mayorista(db, pedido):
    cliente_id = pedido.get("cliente_id")
    total = _float(pedido.get("total"))

    if not cliente_id or total <= 0:
        return

    db.table("namnam_credito_movimientos").insert({
        "cliente_id": cliente_id,
        "tipo": "Consumo",
        "importe": total,
        "observaciones": f"Pedido #{pedido['id']}",
    }).execute()

    cliente = (
        db.table(table("clientes"))
        .select("*")
        .eq("id", cliente_id)
        .execute()
        .data[0]
    )

    saldo_actual = _float(cliente.get("saldo_cuenta_corriente"))

    db.table(table("clientes")).update({
        "saldo_cuenta_corriente": saldo_actual - total
    }).eq("id", cliente_id).execute()


def _ordenar_familias(familias):
    orden_preferido = [
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

    familias_ordenadas = []
    usadas = set()

    for f in orden_preferido:
        for existente in familias.keys():
            if existente.lower() == f.lower() and existente not in usadas:
                familias_ordenadas.append(existente)
                usadas.add(existente)

    for f in sorted(familias.keys()):
        if f not in usadas:
            familias_ordenadas.append(f)

    return familias_ordenadas


def _init_pedido_cantidades():
    if "pedido_cantidades" not in st.session_state:
        st.session_state["pedido_cantidades"] = {}


def _get_cantidad(producto_id):
    _init_pedido_cantidades()
    return _float(st.session_state["pedido_cantidades"].get(str(producto_id), 0))


def _set_cantidad(producto_id, value):
    _init_pedido_cantidades()
    value = _float(value)
    key = str(producto_id)
    if value <= 0:
        st.session_state["pedido_cantidades"].pop(key, None)
    else:
        st.session_state["pedido_cantidades"][key] = value


def _sync_cantidad_widget(producto_id, widget_key):
    _set_cantidad(producto_id, st.session_state.get(widget_key, 0))


def _limpiar_pedido():
    st.session_state["pedido_cantidades"] = {}
    for k in list(st.session_state.keys()):
        if str(k).startswith("cant_widget_"):
            del st.session_state[k]


def _resumen_items(familias_ordenadas, familias, cliente):
    _init_pedido_cantidades()
    items = []
    resumen = []

    for familia in familias_ordenadas:
        subtotal_familia = 0.0
        unidades_familia = 0.0

        for p in familias[familia]:
            precio = _precio_para_cliente(p, cliente)
            cant = _get_cantidad(p["id"])
            subtotal = cant * precio

            if cant > 0:
                unidades_familia += cant
                subtotal_familia += subtotal
                items.append({
                    "producto_id": p["id"],
                    "producto_nombre": p["nombre"],
                    "cantidad": cant,
                    "precio_unitario": precio,
                    "subtotal": subtotal,
                })

        resumen.append({
            "familia": familia,
            "subtotal": subtotal_familia,
            "unidades": unidades_familia,
        })

    return items, resumen


def render():
    header("📝 Pedidos", "Crear pedido por familias, cobrar o descontar saldo mayorista")
    db = require_db()
    _init_pedido_cantidades()

    productos = [p for p in fetch_table("productos") if p.get("activo")]
    clientes = [c for c in fetch_table("clientes") if c.get("activo")]

    st.subheader("➕ Crear pedido")

    if not productos:
        st.warning("Primero cargá productos.")
    else:
        cliente_opciones = {_nombre_cliente(c): c for c in clientes}

        cliente_txt = st.selectbox(
            "Cliente",
            ["Venta mostrador / Consumidor Final"] + list(cliente_opciones.keys())
        )

        cliente = None
        cliente_id = None
        cliente_nombre = "Venta mostrador"

        if cliente_txt != "Venta mostrador / Consumidor Final":
            cliente = cliente_opciones[cliente_txt]
            cliente_id = cliente["id"]
            cliente_nombre = _nombre_cliente(cliente).split(" - ")[0]

        cliente_manual = st.text_input("Nombre manual si no querés guardar cliente")

        if cliente_manual.strip():
            cliente_nombre = cliente_manual.strip()
            cliente_id = None
            cliente = None

        obs = st.text_area("Observaciones")
        tipo_cliente = (cliente or {}).get("tipo_cliente") or "Minorista"

        familias = {}
        for p in productos:
            familia = _familia_producto(p)
            familias.setdefault(familia, []).append(p)

        familias_ordenadas = _ordenar_familias(familias)
        items, resumen_familias = _resumen_items(familias_ordenadas, familias, cliente)

        st.markdown("### 🧾 Productos por familia")

        if "familia_actual_pedido" not in st.session_state:
            st.session_state["familia_actual_pedido"] = familias_ordenadas[0]

        if st.session_state["familia_actual_pedido"] not in familias_ordenadas:
            st.session_state["familia_actual_pedido"] = familias_ordenadas[0]

        labels_radio = [f"{_emoji_familia(f)} {f}" for f in familias_ordenadas]
        label_to_family = {f"{_emoji_familia(f)} {f}": f for f in familias_ordenadas}

        current_family = st.session_state["familia_actual_pedido"]
        current_label = f"{_emoji_familia(current_family)} {current_family}"
        current_index = labels_radio.index(current_label) if current_label in labels_radio else 0

        selected_label = st.radio(
            "Familia",
            labels_radio,
            index=current_index,
            horizontal=True,
            key="radio_familia_pedido_estable"
        )

        familia_actual = label_to_family[selected_label]
        st.session_state["familia_actual_pedido"] = familia_actual

        resumen_actual = next(
            (r for r in resumen_familias if r["familia"] == familia_actual),
            {"subtotal": 0, "unidades": 0}
        )

        st.markdown(f"### {_emoji_familia(familia_actual)} {familia_actual}")

        c_fam1, c_fam2 = st.columns(2)
        c_fam1.metric("Cantidad en familia", f"{resumen_actual['unidades']:g}")
        c_fam2.metric("Subtotal familia", money(resumen_actual["subtotal"]))

        st.divider()

        productos_familia = familias[familia_actual]

        for p in productos_familia:
            c1, c2, c3 = st.columns([4, 1, 1])

            unidad = p.get("unidad") or "unidad"
            precio = _precio_para_cliente(p, cliente)
            producto_id = p["id"]
            widget_key = f"cant_widget_{producto_id}"

            if widget_key not in st.session_state:
                st.session_state[widget_key] = _get_cantidad(producto_id)

            c1.write(f"**{p['nombre']}**")
            c1.caption(f"{money(precio)} / {unidad}")

            cant = c2.number_input(
                "Cant.",
                min_value=0.0,
                step=1.0,
                key=widget_key,
                on_change=_sync_cantidad_widget,
                args=(producto_id, widget_key),
            )

            subtotal = _float(cant) * precio
            c3.write("Subtotal")
            c3.markdown(f"**{money(subtotal)}**")

        items, resumen_familias = _resumen_items(familias_ordenadas, familias, cliente)
        total = sum(i["subtotal"] for i in items)

        st.divider()

        ctot1, ctot2 = st.columns([2, 1])
        with ctot1:
            st.markdown("### 📋 Resumen por familia")
            resumen_df = [
                {
                    "Familia": f"{_emoji_familia(r['familia'])} {r['familia']}",
                    "Cantidad": r["unidades"],
                    "Subtotal": money(r["subtotal"]),
                }
                for r in resumen_familias
                if r["subtotal"] > 0
            ]

            if resumen_df:
                st.dataframe(pd.DataFrame(resumen_df), use_container_width=True, hide_index=True)
            else:
                st.info("Todavía no cargaste productos.")

        with ctot2:
            st.markdown("### 🧮 Total pedido")
            st.markdown(f"# {money(total)}")

        if tipo_cliente == "Mayorista":
            forma_cobro = st.radio("Cobro", FORMAS_MAYORISTA, horizontal=True)

            if forma_cobro == "Cobrar ahora":
                forma_pago = st.selectbox(
                    "Forma de pago",
                    ["Efectivo", "Transferencia", "Mercado Pago"]
                )
            else:
                forma_pago = "Saldo mayorista"
                saldo = _float(cliente.get("saldo_cuenta_corriente") if cliente else 0)
                disponible_final = saldo - total

                if disponible_final < 0:
                    st.error(f"⚠ Este pedido deja deuda de {money(abs(disponible_final))}")
                else:
                    st.success(f"Saldo luego del pedido: {money(disponible_final)}")
        else:
            forma_pago = st.selectbox("Forma de pago", FORMAS_MINORISTA)
            forma_cobro = "Cobrado" if forma_pago != "Pendiente" else "Pendiente"

        col_guardar, col_limpiar = st.columns([1, 1])

        with col_guardar:
            guardar = st.button("Guardar pedido")

        with col_limpiar:
            limpiar = st.button("Limpiar cantidades")

        if limpiar:
            _limpiar_pedido()
            st.rerun()

        if guardar:
            if not items:
                st.warning("Agregá al menos un producto.")
            else:
                tipo_cobro = "Pendiente"
                pagado = False

                if tipo_cliente == "Mayorista" and forma_cobro == "Usar saldo mayorista":
                    tipo_cobro = "Cuenta corriente"
                    pagado = True
                elif forma_pago != "Pendiente":
                    tipo_cobro = "Cobrado"
                    pagado = True

                pedido = db.table(table("pedidos")).insert({
                    "cliente_id": cliente_id,
                    "cliente_nombre": cliente_nombre,
                    "estado": "Pendiente",
                    "total": total,
                    "observaciones": obs,
                    "pagado": pagado,
                    "forma_pago": forma_pago,
                    "tipo_cobro": tipo_cobro,
                }).execute().data[0]

                for it in items:
                    it["pedido_id"] = pedido["id"]

                db.table(table("pedido_detalles")).insert(items).execute()

                if tipo_cobro == "Cobrado":
                    _registrar_caja(db, pedido, forma_pago)

                if tipo_cobro == "Cuenta corriente":
                    _usar_saldo_mayorista(db, pedido)

                _limpiar_pedido()
                st.success("Pedido guardado.")
                st.rerun()

    st.divider()
    st.subheader("Pedidos")
    pedidos = fetch_table("pedidos", "fecha")

    if not pedidos:
        st.info("Todavía no hay pedidos.")
        return

    for p in reversed(pedidos):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 3, 2, 2])

            c1.markdown(f"### #{p['id']}")
            c2.write(f"**Cliente:** {p.get('cliente_nombre') or 'Sin cliente'}")
            c2.caption(f"Cobro: {p.get('tipo_cobro') or 'Pendiente'} · {p.get('forma_pago') or '-'}")

            estado_actual = p.get("estado") if p.get("estado") in ESTADOS else "Pendiente"

            nuevo_estado = c3.selectbox(
                "Estado",
                ESTADOS,
                index=ESTADOS.index(estado_actual),
                key=f"e{p['id']}"
            )

            c4.markdown(f"### {money(p.get('total'))}")

            if p.get("tipo_cobro") == "Cobrado":
                c4.success("Pagado")
            elif p.get("tipo_cobro") == "Cuenta corriente":
                c4.warning("Descontado de saldo")
            else:
                c4.info("Pendiente")

            if st.button("Actualizar estado", key=f"up{p['id']}"):
                db.table(table("pedidos")).update({
                    "estado": nuevo_estado
                }).eq("id", p["id"]).execute()

                st.success("Estado actualizado.")
                st.rerun()

            items_pedido = (
                db.table(table("pedido_detalles"))
                .select("producto_nombre,cantidad,precio_unitario,subtotal")
                .eq("pedido_id", p["id"])
                .execute()
                .data
            )

            if items_pedido:
                st.dataframe(pd.DataFrame(items_pedido), use_container_width=True, hide_index=True)

            if p.get("observaciones"):
                st.caption(p["observaciones"])
