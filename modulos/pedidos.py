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


def render():
    header("📝 Pedidos", "Crear pedido por familias, cobrar o descontar saldo mayorista")
    db = require_db()

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

        st.markdown("### Productos por familia")

        items = []
        subtotales_familia = {}

        for familia in familias_ordenadas:
            productos_familia = familias[familia]
            subtotal_familia = 0.0

            for p in productos_familia:
                precio_tmp = _precio_para_cliente(p, cliente)
                cant_tmp = _float(st.session_state.get(f"cant_{p['id']}", 0))
                subtotal_familia += cant_tmp * precio_tmp

            subtotales_familia[familia] = subtotal_familia
            titulo = f"{familia} — {money(subtotal_familia)}"

            with st.expander(titulo, expanded=False):
                for p in productos_familia:
                    c1, c2, c3 = st.columns([4, 1, 1])

                    unidad = p.get("unidad") or "unidad"
                    precio = _precio_para_cliente(p, cliente)

                    c1.write(f"**{p['nombre']}**")
                    c1.caption(f"{money(precio)} / {unidad}")

                    cant = c2.number_input(
                        "Cant.",
                        min_value=0.0,
                        step=1.0,
                        key=f"cant_{p['id']}"
                    )

                    subtotal = cant * precio

                    if cant > 0:
                        items.append({
                            "producto_id": p["id"],
                            "producto_nombre": p["nombre"],
                            "cantidad": cant,
                            "precio_unitario": precio,
                            "subtotal": subtotal,
                        })

                    c3.write("Subtotal")
                    c3.markdown(f"**{money(subtotal)}**")

        total = sum(i["subtotal"] for i in items)

        st.divider()

        ctot1, ctot2 = st.columns([2, 1])
        with ctot1:
            st.markdown("### Resumen por familia")
            resumen = [
                {"Familia": f, "Subtotal": money(v)}
                for f, v in subtotales_familia.items()
                if v > 0
            ]

            if resumen:
                st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)
            else:
                st.info("Todavía no cargaste productos.")

        with ctot2:
            st.markdown("### Total pedido")
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

        if st.button("Guardar pedido"):
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

            items = (
                db.table(table("pedido_detalles"))
                .select("producto_nombre,cantidad,precio_unitario,subtotal")
                .eq("pedido_id", p["id"])
                .execute()
                .data
            )

            if items:
                st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)

            if p.get("observaciones"):
                st.caption(p["observaciones"])
