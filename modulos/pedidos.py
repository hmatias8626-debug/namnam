import unicodedata

import pandas as pd
import streamlit as st

from services.auth import current_user
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


def _cliente_es_mayorista(cliente):
    if not cliente:
        return False

    valor = str(cliente.get("tipo_cliente") or "").strip().lower()
    if valor == "mayorista":
        return True

    # Por si alguna vez quedó guardado como booleano/campo alternativo.
    if cliente.get("mayorista") is True or cliente.get("es_mayorista") is True:
        return True

    return False


def _usuario_actual_texto():
    user = current_user() or {}
    return (
        user.get("usuario")
        or user.get("nombre")
        or user.get("email")
        or user.get("rol")
        or "admin"
    )


def _recalcular_pedido_sql(db, pedido_id, tipo_venta):
    try:
        res = db.rpc(
            "namnam_recalcular_pedido_tipo",
            {
                "p_pedido_id": int(pedido_id),
                "p_tipo": tipo_venta,
                "p_usuario": _usuario_actual_texto(),
            },
        ).execute()

        data = res.data
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data

        return {"ok": True, "items_modificados": 0, "cajas_actualizadas": 0}
    except Exception as e:
        st.error("No pude recalcular con la función SQL. Ejecutá el SQL incluido y reiniciá la app.")
        st.exception(e)
        return None


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

def _familia_igual(familia_producto, familia_elegida):
    return str(familia_producto or "").strip().lower() == str(familia_elegida or "").strip().lower()


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
    if "bombita" in f or "bomba" in f:
        return "🧆"
    if "sandwich" in f or "sándwich" in f:
        return "🥪"
    if "torta" in f:
        return "🍰"
    return "📦"


def _precio_producto(producto, tipo_venta):
    if not producto:
        return 0.0

    mayorista_cols = [
        "precio_mayorista",
        "precio_mayor",
        "precio_mayorista_venta",
        "precio_venta_mayorista",
        "precio_wholesale",
        "mayorista",
    ]

    minorista_cols = [
        "precio_venta",
        "precio_minorista",
        "precio",
        "precio_publico",
        "venta",
    ]

    cols = mayorista_cols if tipo_venta == "Mayorista" else minorista_cols

    for col in cols:
        if col in producto and producto.get(col) not in (None, ""):
            val = _float(producto.get(col))
            if val > 0:
                return val

    # Fallback: si no hay mayorista cargado, usa minorista.
    for col in minorista_cols:
        if col in producto and producto.get(col) not in (None, ""):
            val = _float(producto.get(col))
            if val > 0:
                return val

    return 0.0


def _precio_para_tipo(producto, tipo_venta):
    return _precio_producto(producto, tipo_venta)


def _precio_mayorista(producto):
    return _precio_producto(producto, "Mayorista")


def _normalizar_nombre_producto(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = " ".join(texto.split())
    return texto




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
        "Bombas de papa",
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


def _leer_promos_combinadas(db):
    try:
        return (
            db.table("namnam_promos_combinadas")
            .select("*")
            .eq("activo", True)
            .order("id")
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _leer_grupos_promo_combinada(db, promo_id):
    try:
        return (
            db.table("namnam_promos_combinadas_grupos")
            .select("*")
            .eq("promo_id", promo_id)
            .order("orden")
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _productos_para_promo_flexible(productos, promo):
    familia = str(promo.get("familia_incluida") or "").strip().lower()
    excluir = str(promo.get("texto_excluir") or "").strip().lower()
    res = []

    for p in productos:
        fam = _familia_producto(p).lower()
        nombre = str(p.get("nombre") or "").lower()

        if familia and not _familia_igual(fam, familia):
            continue

        if excluir and (excluir in fam or excluir in nombre):
            continue

        res.append(p)

    return res


def _productos_para_grupo_combinado(productos, grupo):
    familia = str(grupo.get("familia") or "").strip().lower()
    excluir = str(grupo.get("texto_excluir") or "").strip().lower()
    res = []

    for p in productos:
        fam = _familia_producto(p).lower()
        nombre = str(p.get("nombre") or "").lower()

        if familia and not _familia_igual(fam, familia):
            continue

        if excluir and (excluir in fam or excluir in nombre):
            continue

        res.append(p)

    return res


def _init_pedido_cantidades():
    if "pedido_cantidades" not in st.session_state:
        st.session_state["pedido_cantidades"] = {}
    if "pedido_promos" not in st.session_state:
        st.session_state["pedido_promos"] = {}
    if "pedido_promos_flex" not in st.session_state:
        st.session_state["pedido_promos_flex"] = {}
    if "pedido_promos_combo" not in st.session_state:
        st.session_state["pedido_promos_combo"] = {}


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


def _get_promo_qty(promo_id):
    _init_pedido_cantidades()
    return _float(st.session_state["pedido_promos"].get(str(promo_id), 0))


def _set_promo_qty(promo_id, value):
    _init_pedido_cantidades()
    value = _float(value)
    key = str(promo_id)
    if value <= 0:
        st.session_state["pedido_promos"].pop(key, None)
    else:
        st.session_state["pedido_promos"][key] = value


def _sync_promo_widget(promo_id, widget_key):
    _set_promo_qty(promo_id, st.session_state.get(widget_key, 0))


def _flex_key(promo_id, producto_id):
    return f"{promo_id}:{producto_id}"


def _get_flex_qty(promo_id, producto_id):
    _init_pedido_cantidades()
    return _float(st.session_state["pedido_promos_flex"].get(_flex_key(promo_id, producto_id), 0))


def _set_flex_qty(promo_id, producto_id, value):
    _init_pedido_cantidades()
    key = _flex_key(promo_id, producto_id)
    value = _float(value)

    if value <= 0:
        st.session_state["pedido_promos_flex"].pop(key, None)
    else:
        st.session_state["pedido_promos_flex"][key] = value


def _sync_flex_widget(promo_id, producto_id, widget_key):
    _set_flex_qty(promo_id, producto_id, st.session_state.get(widget_key, 0))


def _flex_total_seleccionado(promo_id):
    _init_pedido_cantidades()
    prefix = f"{promo_id}:"
    return sum(
        _float(v)
        for k, v in st.session_state["pedido_promos_flex"].items()
        if str(k).startswith(prefix)
    )


def _combo_key(promo_id, grupo_id, producto_id):
    return f"{promo_id}:{grupo_id}:{producto_id}"


def _get_combo_qty(promo_id, grupo_id, producto_id):
    _init_pedido_cantidades()
    return _float(st.session_state["pedido_promos_combo"].get(_combo_key(promo_id, grupo_id, producto_id), 0))


def _set_combo_qty(promo_id, grupo_id, producto_id, value):
    _init_pedido_cantidades()
    key = _combo_key(promo_id, grupo_id, producto_id)
    value = _float(value)

    if value <= 0:
        st.session_state["pedido_promos_combo"].pop(key, None)
    else:
        st.session_state["pedido_promos_combo"][key] = value


def _sync_combo_widget(promo_id, grupo_id, producto_id, widget_key):
    _set_combo_qty(promo_id, grupo_id, producto_id, st.session_state.get(widget_key, 0))


def _combo_total_grupo(promo_id, grupo_id):
    _init_pedido_cantidades()
    prefix = f"{promo_id}:{grupo_id}:"
    return sum(
        _float(v)
        for k, v in st.session_state["pedido_promos_combo"].items()
        if str(k).startswith(prefix)
    )


def _limpiar_pedido():
    st.session_state["pedido_cantidades"] = {}
    st.session_state["pedido_promos"] = {}
    st.session_state["pedido_promos_flex"] = {}
    st.session_state["pedido_promos_combo"] = {}

    for k in list(st.session_state.keys()):
        if (
            str(k).startswith("cant_widget_")
            or str(k).startswith("promo_widget_")
            or str(k).startswith("flex_widget_")
            or str(k).startswith("combo_widget_")
        ):
            del st.session_state[k]


def _resumen_items(familias_ordenadas, familias, tipo_venta):
    _init_pedido_cantidades()
    items = []
    resumen = []

    for familia in familias_ordenadas:
        subtotal_familia = 0.0
        unidades_familia = 0.0

        for p in familias[familia]:
            precio = _precio_para_tipo(p, tipo_venta)
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


def _armar_items_promos_fijas(promos):
    items = []

    for promo in promos:
        cant = _get_promo_qty(promo["id"])
        if cant <= 0:
            continue

        precio = _float(promo.get("precio"))
        subtotal = cant * precio

        items.append({
            "producto_id": None,
            "producto_nombre": promo.get("nombre"),
            "cantidad": cant,
            "precio_unitario": precio,
            "subtotal": subtotal,
            "promo_id": promo["id"],
        })

    return items


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
            "producto_id": None,
            "producto_nombre": promo.get("nombre"),
            "cantidad": 1,
            "precio_unitario": precio,
            "subtotal": precio,
            "promo_flexible_id": promo_id,
            "promo_flexible_nombre": promo.get("nombre"),
            "detalle_flexible": detalle,
        })

    return items


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
                    detalle.append({
                        "grupo_id": grupo_id,
                        "familia": grupo.get("familia"),
                        "producto_id": p["id"],
                        "producto_nombre": p.get("nombre"),
                        "cantidad": cant,
                    })

        if not completa:
            continue

        precio = _float(promo.get("precio"))

        items.append({
            "producto_id": None,
            "producto_nombre": promo.get("nombre"),
            "cantidad": 1,
            "precio_unitario": precio,
            "subtotal": precio,
            "promo_combinada_id": promo_id,
            "promo_combinada_nombre": promo.get("nombre"),
            "detalle_combinada": detalle,
        })

    return items


def _render_controles_producto(producto_id, widget_key):
    c1, c2, c3 = st.columns([1, 1, 1])
    if c1.button("−", key=f"menos_{widget_key}"):
        _set_cantidad(producto_id, max(0, _get_cantidad(producto_id) - 1))
        st.rerun()

    if widget_key not in st.session_state:
        st.session_state[widget_key] = _get_cantidad(producto_id)

    c2.number_input(
        "Cant.",
        min_value=0.0,
        step=1.0,
        key=widget_key,
        label_visibility="collapsed",
        on_change=_sync_cantidad_widget,
        args=(producto_id, widget_key),
    )

    if c3.button("➕", key=f"mas_{widget_key}"):
        _set_cantidad(producto_id, _get_cantidad(producto_id) + 1)
        st.rerun()


def _guardar_pedido(db, pedido, items):
    detalles_para_insertar = []
    flex_items_para_insertar = []
    combo_items_para_insertar = []

    for it in items:
        it_db = dict(it)
        detalle_flexible = it_db.pop("detalle_flexible", None)
        detalle_combinada = it_db.pop("detalle_combinada", None)

        it_db["pedido_id"] = pedido["id"]
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
                combo_items_para_insertar.append({
                    "pedido_id": pedido["id"],
                    "promo_combinada_id": it.get("promo_combinada_id"),
                    "grupo_id": det.get("grupo_id"),
                    "familia": det.get("familia"),
                    "producto_id": det.get("producto_id"),
                    "producto_nombre": det.get("producto_nombre"),
                    "cantidad": det.get("cantidad"),
                })

    if detalles_para_insertar:
        db.table(table("pedido_detalles")).insert(detalles_para_insertar).execute()

    if flex_items_para_insertar:
        db.table("namnam_pedido_promo_flexible_items").insert(flex_items_para_insertar).execute()

    if combo_items_para_insertar:
        db.table("namnam_pedido_promo_combinada_items").insert(combo_items_para_insertar).execute()


def _actualizar_pedido_admin(db, pedido_id, cliente_id, cliente_nombre, tipo_cliente, estado, forma_pago, tipo_cobro, observaciones):
    update_data = {
        "cliente_id": cliente_id,
        "cliente_nombre": cliente_nombre,
        "estado": estado,
        "forma_pago": forma_pago,
        "tipo_cobro": tipo_cobro,
        "observaciones": observaciones,
        "tipo_cliente": tipo_cliente,
    }

    try:
        db.table(table("pedidos")).update(update_data).eq("id", pedido_id).execute()
    except Exception:
        update_data.pop("tipo_cliente", None)
        db.table(table("pedidos")).update(update_data).eq("id", pedido_id).execute()


def _leer_productos_cache(db):
    try:
        productos = db.table(table("productos")).select("*").execute().data or []
    except Exception:
        productos = []

    por_id = {}
    por_nombre = {}

    for p in productos:
        if p.get("id") is not None:
            por_id[str(p.get("id"))] = p

        nombres_posibles = [
            p.get("nombre"),
            p.get("producto_nombre"),
            p.get("descripcion"),
            p.get("detalle"),
        ]

        for nom in nombres_posibles:
            n = _normalizar_nombre_producto(nom)
            if n:
                por_nombre[n] = p

    return productos, por_id, por_nombre


def _buscar_producto_para_detalle(det, por_id, por_nombre, productos):
    producto_id = det.get("producto_id")

    if producto_id is not None and str(producto_id) in por_id:
        return por_id[str(producto_id)]

    nombre_det = _normalizar_nombre_producto(det.get("producto_nombre"))

    if nombre_det in por_nombre:
        return por_nombre[nombre_det]

    # Búsqueda flexible: si el nombre del detalle contiene al producto o al revés.
    for p in productos:
        nombres_posibles = [
            p.get("nombre"),
            p.get("producto_nombre"),
            p.get("descripcion"),
            p.get("detalle"),
        ]

        for nom in nombres_posibles:
            nom_norm = _normalizar_nombre_producto(nom)
            if not nom_norm:
                continue

            if nombre_det == nom_norm or nombre_det in nom_norm or nom_norm in nombre_det:
                return p

    return None


def _registrar_auditoria_pedido(db, pedido_id, accion, antes, despues):
    user = current_user() or {}
    usuario = (
        user.get("usuario")
        or user.get("nombre")
        or user.get("email")
        or user.get("rol")
        or "admin"
    )

    try:
        db.table("namnam_pedidos_auditoria").insert({
            "pedido_id": pedido_id,
            "usuario": usuario,
            "accion": accion,
            "antes": antes,
            "despues": despues,
        }).execute()
    except Exception:
        pass


def _actualizar_caja_por_pedido(db, pedido_id, nuevo_total):
    actualizados = 0

    try:
        movimientos = (
            db.table(table("caja"))
            .select("*")
            .eq("pedido_id", pedido_id)
            .execute()
            .data
            or []
        )

        for mov in movimientos:
            db.table(table("caja")).update({
                "importe": nuevo_total,
                "observaciones": f"{mov.get('observaciones') or ''} | Importe actualizado por modificación del pedido #{pedido_id}",
            }).eq("id", mov["id"]).execute()
            actualizados += 1
    except Exception:
        pass

    return actualizados


def _recalcular_precios_pedido(db, pedido_id, tipo_venta):
    """Recalcula precios de productos normales en un pedido ya guardado.
    Busca productos por id, nombre exacto y nombre normalizado.
    Actualiza detalle, total del pedido, caja vinculada y auditoría.
    Las promos mantienen precio de promo.
    """
    pedido_antes_data = (
        db.table(table("pedidos"))
        .select("*")
        .eq("id", pedido_id)
        .execute()
        .data
        or []
    )
    pedido_antes = pedido_antes_data[0] if pedido_antes_data else {}

    detalles = (
        db.table(table("pedido_detalles"))
        .select("*")
        .eq("pedido_id", pedido_id)
        .execute()
        .data
        or []
    )

    productos, por_id, por_nombre, = _leer_productos_cache(db)

    total_anterior = _float(pedido_antes.get("total"))
    total_nuevo = 0.0
    cambios = []
    sin_producto = []

    for det in detalles:
        cantidad = _float(det.get("cantidad"))
        precio_anterior = _float(det.get("precio_unitario"))

        es_promo = bool(
            det.get("promo_id")
            or det.get("promo_flexible_id")
            or det.get("promo_combinada_id")
            or det.get("promo_flexible_nombre")
            or det.get("promo_combinada_nombre")
        )

        precio_nuevo = precio_anterior
        producto_encontrado = None

        if not es_promo:
            producto_encontrado = _buscar_producto_para_detalle(det, por_id, por_nombre, productos)

            if producto_encontrado:
                precio_detectado = _precio_para_tipo(producto_encontrado, tipo_venta)
                if precio_detectado > 0:
                    precio_nuevo = precio_detectado
            else:
                sin_producto.append(det.get("producto_nombre"))

        subtotal_nuevo = cantidad * precio_nuevo
        total_nuevo += subtotal_nuevo

        cambio = {
            "detalle_id": det.get("id"),
            "producto": det.get("producto_nombre"),
            "cantidad": cantidad,
            "precio_anterior": precio_anterior,
            "precio_nuevo": precio_nuevo,
            "subtotal_anterior": _float(det.get("subtotal")),
            "subtotal_nuevo": subtotal_nuevo,
            "producto_encontrado": bool(producto_encontrado),
            "es_promo": es_promo,
        }

        if precio_nuevo != precio_anterior or _float(det.get("subtotal")) != subtotal_nuevo:
            cambios.append(cambio)

        db.table(table("pedido_detalles")).update({
            "precio_unitario": precio_nuevo,
            "subtotal": subtotal_nuevo,
        }).eq("id", det["id"]).execute()

    db.table(table("pedidos")).update({
        "total": total_nuevo,
        "tipo_cliente": tipo_venta,
    }).eq("id", pedido_id).execute()

    cajas_actualizadas = _actualizar_caja_por_pedido(db, pedido_id, total_nuevo)

    _registrar_auditoria_pedido(
        db,
        pedido_id,
        "Recalcular precios por cambio de tipo de cliente",
        {
            "tipo_cliente_anterior": pedido_antes.get("tipo_cliente"),
            "total_anterior": total_anterior,
        },
        {
            "tipo_cliente_nuevo": tipo_venta,
            "total_nuevo": total_nuevo,
            "cambios": cambios,
            "sin_producto": sin_producto,
            "cajas_actualizadas": cajas_actualizadas,
        },
    )

    return total_nuevo, cambios, sin_producto, cajas_actualizadas


def render():
    header("📝 Pedidos", "Crear pedido por familias, promos y precios minorista/mayorista")
    db = require_db()
    user = current_user() or {}
    es_admin = user.get("rol") == "admin"
    _init_pedido_cantidades()

    # Limpieza de claves viejas que rompían en celular/cache
    for old_key in list(st.session_state.keys()):
    if "pedido_tipo" in str(old_key):
        del st.session_state[old_key]

    st.write("DEBUG SESSION:", list(st.session_state.keys()))

    productos = [p for p in fetch_table("productos") if p.get("activo")]
    clientes = [c for c in fetch_table("clientes") if c.get("activo")]
    promos = _leer_promos(db)
    promos_flexibles = _leer_promos_flexibles(db)
    promos_combinadas = _leer_promos_combinadas(db)
    grupos_combinadas = {
        promo["id"]: _leer_grupos_promo_combinada(db, promo["id"])
        for promo in promos_combinadas
    }

    st.subheader("➕ Crear pedido")

    if not productos and not promos and not promos_flexibles and not promos_combinadas:
        st.warning("Primero cargá productos o promociones.")
    else:
        cliente_opciones = {_nombre_cliente(c): c for c in clientes}

        c_cliente, c_tipo = st.columns([2, 1])

        cliente_txt = c_cliente.selectbox(
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

        cliente_mayorista = _cliente_es_mayorista(cliente)

        if cliente_mayorista:
            tipo_venta = "Mayorista"
            c_tipo.markdown("**Tipo de venta**")
            c_tipo.success("Mayorista")
            c_tipo.caption("Cliente mayorista: precio mayorista obligatorio.")
        else:
            tipo_default = (cliente or {}).get("tipo_cliente") or "Minorista"
            tipo_index = 1 if tipo_default == "Mayorista" else 0

            tipo_venta = c_tipo.radio(
                "Tipo de venta",
                ["Minorista", "Mayorista"],
                index=tipo_index,
                horizontal=True,
                key="pedido_tipo_venta_radio",
                help="Elegí si este pedido usa precio minorista o mayorista.",

        cliente_manual = st.text_input("Nombre manual si no querés guardar cliente")

        if cliente_manual.strip():
            cliente_nombre = cliente_manual.strip()
            cliente_id = None
            cliente = None

        obs = st.text_area("Observaciones")

        familias = {}
        for p in productos:
            familia = _familia_producto(p)
            familias.setdefault(familia, []).append(p)

        familias_ordenadas = _ordenar_familias(familias) if familias else []
        items_productos, resumen_familias = _resumen_items(familias_ordenadas, familias, tipo_venta)
        items_promos_fijas = _armar_items_promos_fijas(promos)
        items_flexibles = _armar_items_flexibles(productos, promos_flexibles)
        items_combinados = _armar_items_combinados(productos, promos_combinadas, grupos_combinadas)

        items = items_productos + items_promos_fijas + items_flexibles + items_combinados
        total = sum(i["subtotal"] for i in items)

        tab_prod, tab_promos, tab_resumen = st.tabs([
            "📦 Productos",
            "🏷️ Promociones",
            "🧾 Resumen",
        ])

        with tab_prod:
            st.markdown("### 🧾 Productos por familia")

            if not familias_ordenadas:
                st.info("No hay productos cargados.")
            else:
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

                for p in familias[familia_actual]:
                    c1, c2, c3 = st.columns([4, 1, 1])

                    unidad = p.get("unidad") or "unidad"
                    precio_usado = _precio_para_tipo(p, tipo_venta)
                    precio_min = _float(p.get("precio_venta"))
                    precio_may = _precio_mayorista(p)
                    producto_id = p["id"]
                    widget_key = f"cant_widget_{producto_id}"

                    c1.write(f"**{p['nombre']}**")
                    c1.caption(
                        f"Minorista: {money(precio_min)} · Mayorista: {money(precio_may)} · Usando: {money(precio_usado)} / {unidad}"
                    )

                    if widget_key not in st.session_state:
                        st.session_state[widget_key] = _get_cantidad(producto_id)

                    cant = c2.number_input(
                        "Cant.",
                        min_value=0.0,
                        step=1.0,
                        key=widget_key,
                        on_change=_sync_cantidad_widget,
                        args=(producto_id, widget_key),
                    )

                    subtotal = _float(cant) * precio_usado
                    c3.write("Subtotal")
                    c3.markdown(f"**{money(subtotal)}**")

        with tab_promos:
            st.markdown("### 🏷️ Promociones")
            st.caption("Acá aparecen las promociones fijas y las promociones por familias/categorías.")

            if not promos and not promos_combinadas:
                st.info("No hay promociones activas.")

            if promos:
                st.markdown("#### Promos fijas")
                for promo in promos:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([4, 1, 1])
                        c1.markdown(f"**{promo.get('nombre')}**")
                        c1.caption(promo.get("descripcion") or "")
                        c1.write(f"Precio: **{money(promo.get('precio'))}**")

                        detalles = _leer_detalle_promo(db, promo["id"])
                        if detalles:
                            with c1.expander("Ver productos incluidos"):
                                st.dataframe(pd.DataFrame(detalles), use_container_width=True, hide_index=True)

                        widget_key = f"promo_widget_{promo['id']}"
                        if widget_key not in st.session_state:
                            st.session_state[widget_key] = _get_promo_qty(promo["id"])

                        cant = c2.number_input(
                            "Cant.",
                            min_value=0.0,
                            step=1.0,
                            key=widget_key,
                            on_change=_sync_promo_widget,
                            args=(promo["id"], widget_key),
                        )

                        c3.write("Subtotal")
                        c3.markdown(f"**{money(_float(cant) * _float(promo.get('precio')))}**")

            if promos_combinadas:
                st.markdown("#### Promos por familias")

                for promo_combo in promos_combinadas:
                    promo_id = promo_combo["id"]
                    grupos = grupos_combinadas.get(promo_id, [])

                    with st.container(border=True):
                        st.markdown(f"### 🏷️ {promo_combo.get('nombre')}")
                        if promo_combo.get("descripcion"):
                            st.caption(promo_combo.get("descripcion"))
                        st.write(f"Precio promo: **{money(promo_combo.get('precio'))}**")

                        completa = True

                        for grupo in grupos:
                            grupo_id = grupo["id"]
                            requerido = int(_float(grupo.get("cantidad_requerida")))
                            seleccionado = int(_combo_total_grupo(promo_id, grupo_id))

                            if seleccionado != requerido:
                                completa = False

                            with st.expander(f"{grupo.get('familia')} — {seleccionado:g} / {requerido:g}", expanded=True):
                                if seleccionado < requerido:
                                    st.warning(f"Faltan elegir {requerido - seleccionado:g}.")
                                elif seleccionado > requerido:
                                    st.error(f"Te pasaste por {seleccionado - requerido:g}.")
                                else:
                                    st.success("Grupo completo.")

                                productos_grupo = _productos_para_grupo_combinado(productos, grupo)

                                if not productos_grupo:
                                    st.info("No hay productos para este grupo.")
                                else:
                                    for p in productos_grupo:
                                        qty = int(_get_combo_qty(promo_id, grupo_id, p["id"]))
                                        total_grupo = int(_combo_total_grupo(promo_id, grupo_id))
                                        restante = max(0, requerido - total_grupo)

                                        st.markdown(f"**{p.get('nombre')}**")
                                        st.caption(f"{p.get('unidad') or 'unidad'} · grupo {grupo.get('familia')}")

                                        # Botones x1, x2, x3... según la cantidad pedida del grupo.
                                        cols = st.columns(requerido + 1)
                                        for n in range(1, requerido + 1):
                                            # Si el producto ya tiene cantidad, permitimos cambiarla siempre que no se pase.
                                            # Si está en cero, solo permite elegir hasta el restante.
                                            permitido = (qty > 0 and (total_grupo - qty + n) <= requerido) or (qty == 0 and n <= restante)
                                            activo = qty == n
                                            label = f"✓ x{n}" if activo else f"x{n}"

                                            if cols[n - 1].button(
                                                label,
                                                key=f"combo_x{n}_{promo_id}_{grupo_id}_{p['id']}",
                                                disabled=not permitido,
                                            ):
                                                _set_combo_qty(promo_id, grupo_id, p["id"], n)
                                                st.rerun()

                                        if cols[-1].button("🗑️", key=f"combo_del_{promo_id}_{grupo_id}_{p['id']}"):
                                            _set_combo_qty(promo_id, grupo_id, p["id"], 0)
                                            st.rerun()

                        if completa and grupos:
                            st.success("Promo completa. Se suma al pedido.")
                        else:
                            st.info("Completá todos los grupos para sumar la promo.")

        with tab_resumen:
            st.markdown("### 📋 Resumen del pedido")

            if items:
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
                    hide_index=True,
                )
            else:
                st.info("Todavía no cargaste productos ni promos.")

            st.markdown(f"## Total: {money(total)}")

        # recalcular después de tabs
        items_productos, resumen_familias = _resumen_items(familias_ordenadas, familias, tipo_venta)
        items_promos_fijas = _armar_items_promos_fijas(promos)
        items_flexibles = _armar_items_flexibles(productos, promos_flexibles)
        items_combinados = _armar_items_combinados(productos, promos_combinadas, grupos_combinadas)
        items = items_productos + items_promos_fijas + items_flexibles + items_combinados
        total = sum(i["subtotal"] for i in items)

        st.divider()
        ctot1, ctot2 = st.columns([2, 1])

        with ctot1:
            st.markdown("### 🧮 Total pedido")
            st.markdown(f"# {money(total)}")
            st.caption(f"Tipo de venta: {tipo_venta}")

        with ctot2:
            if tipo_venta == "Mayorista":
                forma_cobro = st.radio("Cobro", FORMAS_MAYORISTA, horizontal=False)

                if forma_cobro == "Cobrar ahora":
                    forma_pago = st.selectbox("Forma de pago", ["Efectivo", "Transferencia", "Mercado Pago"])
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
            # Validaciones de promos incompletas
            for promo_flex in promos_flexibles:
                seleccionado = _flex_total_seleccionado(promo_flex["id"])
                requerido = _float(promo_flex.get("cantidad_requerida"))

                if seleccionado > 0 and seleccionado != requerido:
                    st.warning(
                        f"La promo '{promo_flex.get('nombre')}' necesita exactamente {requerido:g} unidades. Ahora tiene {seleccionado:g}."
                    )
                    return

            for promo_combo in promos_combinadas:
                for grupo in grupos_combinadas.get(promo_combo["id"], []):
                    seleccionado = _combo_total_grupo(promo_combo["id"], grupo["id"])
                    requerido = _float(grupo.get("cantidad_requerida"))

                    if seleccionado > 0 and seleccionado != requerido:
                        st.warning(
                            f"La promo '{promo_combo.get('nombre')}' necesita exactamente {requerido:g} de {grupo.get('familia')}. Ahora tiene {seleccionado:g}."
                        )
                        return

            if not items:
                st.warning("Agregá al menos un producto o promo.")
            else:
                tipo_cobro = "Pendiente"
                pagado = False

                if tipo_venta == "Mayorista" and forma_cobro == "Usar saldo mayorista":
                    tipo_cobro = "Cuenta corriente"
                    pagado = True
                elif forma_pago != "Pendiente":
                    tipo_cobro = "Cobrado"
                    pagado = True

                insert_pedido = {
                    "cliente_id": cliente_id,
                    "cliente_nombre": cliente_nombre,
                    "estado": "Pendiente",
                    "total": total,
                    "observaciones": obs,
                    "pagado": pagado,
                    "forma_pago": forma_pago,
                    "tipo_cobro": tipo_cobro,
                    "tipo_cliente": tipo_venta,
                }

                try:
                    pedido = db.table(table("pedidos")).insert(insert_pedido).execute().data[0]
                except Exception:
                    insert_pedido.pop("tipo_cliente", None)
                    pedido = db.table(table("pedidos")).insert(insert_pedido).execute().data[0]

                _guardar_pedido(db, pedido, items)

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

    cliente_opciones_lista = ["Sin cliente / Mostrador"] + [_nombre_cliente(c) for c in clientes]
    cliente_por_label = {_nombre_cliente(c): c for c in clientes}

    for p in reversed(pedidos):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 3, 2, 2])

            c1.markdown(f"### #{p['id']}")
            c2.write(f"**Cliente:** {p.get('cliente_nombre') or 'Sin cliente'}")
            c2.caption(
                f"Tipo: {p.get('tipo_cliente') or '-'} · Cobro: {p.get('tipo_cobro') or 'Pendiente'} · {p.get('forma_pago') or '-'}"
            )

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

            msg_recalculo = st.session_state.get(f"recalculo_msg_{p['id']}")
            if msg_recalculo:
                st.success(msg_recalculo)

            if st.button("Actualizar estado", key=f"up{p['id']}"):
                db.table(table("pedidos")).update({
                    "estado": nuevo_estado
                }).eq("id", p["id"]).execute()

                st.success("Estado actualizado.")
                st.rerun()

            with st.expander("✏️ Editar datos del pedido"):
                cliente_actual_label = "Sin cliente / Mostrador"
                for label, cli in cliente_por_label.items():
                    if cli.get("id") == p.get("cliente_id"):
                        cliente_actual_label = label
                        break

                cedit1, cedit2 = st.columns([2, 1])
                cliente_edit = cedit1.selectbox(
                    "Cliente",
                    cliente_opciones_lista,
                    index=cliente_opciones_lista.index(cliente_actual_label) if cliente_actual_label in cliente_opciones_lista else 0,
                    key=f"pedido_cliente_edit_{p['id']}",
                )

                cliente_edit_obj = None
                cliente_edit_es_mayorista = False

                if cliente_edit != "Sin cliente / Mostrador":
                    cliente_edit_obj = cliente_por_label[cliente_edit]
                    cliente_edit_es_mayorista = _cliente_es_mayorista(cliente_edit_obj)

                tipo_edit_index = 1 if (cliente_edit_es_mayorista or p.get("tipo_cliente") == "Mayorista") else 0

                tipo_edit = cedit2.radio(
                    "Tipo",
                    ["Minorista", "Mayorista"],
                    index=tipo_edit_index,
                    horizontal=True,
                    key=f"pedido_tipo_edit_{p['id']}",
                    disabled=cliente_edit_es_mayorista,
                )

                if cliente_edit_es_mayorista:
                    tipo_edit = "Mayorista"
                    cedit2.success("Mayorista obligatorio.")

                if cliente_edit == "Sin cliente / Mostrador":
                    cliente_id_edit = None
                    cliente_nombre_edit = st.text_input(
                        "Nombre cliente",
                        value=p.get("cliente_nombre") or "Venta mostrador",
                        key=f"pedido_cliente_nombre_edit_{p['id']}",
                    )
                else:
                    cli = cliente_edit_obj
                    cliente_id_edit = cli.get("id")
                    cliente_nombre_edit = _nombre_cliente(cli).split(" - ")[0]
                    st.caption(f"Cliente seleccionado: {cliente_nombre_edit}")

                cedit3, cedit4 = st.columns(2)
                forma_pago_edit = cedit3.selectbox(
                    "Forma de pago",
                    ["Efectivo", "Transferencia", "Mercado Pago", "Pendiente", "Saldo mayorista"],
                    index=0 if not p.get("forma_pago") else (
                        ["Efectivo", "Transferencia", "Mercado Pago", "Pendiente", "Saldo mayorista"].index(p.get("forma_pago"))
                        if p.get("forma_pago") in ["Efectivo", "Transferencia", "Mercado Pago", "Pendiente", "Saldo mayorista"]
                        else 0
                    ),
                    key=f"pedido_forma_edit_{p['id']}",
                )

                tipo_cobro_edit = cedit4.selectbox(
                    "Tipo de cobro",
                    ["Pendiente", "Cobrado", "Cuenta corriente"],
                    index=["Pendiente", "Cobrado", "Cuenta corriente"].index(p.get("tipo_cobro"))
                    if p.get("tipo_cobro") in ["Pendiente", "Cobrado", "Cuenta corriente"] else 0,
                    key=f"pedido_cobro_edit_{p['id']}",
                )

                obs_edit = st.text_area(
                    "Observaciones",
                    value=p.get("observaciones") or "",
                    key=f"pedido_obs_edit_{p['id']}",
                )

                recalcular_precios = st.checkbox(
                    "Recalcular precios según tipo seleccionado",
                    value=True,
                    key=f"pedido_recalcular_precios_{p['id']}",
                    help="Si cambiás de Minorista a Mayorista, actualiza los precios de los productos normales y el total. Las promos mantienen su precio de promo.",
                )

                if es_admin:
                    if st.button("🔥 Aplicar precios del tipo seleccionado ahora", key=f"forzar_recalculo_sql_{p['id']}"):
                        resultado_recalculo = _recalcular_pedido_sql(db, p["id"], tipo_edit)
                        if resultado_recalculo:
                            st.success(
                                f"Listo. Ítems modificados: {resultado_recalculo.get('items_modificados')}. "
                                f"Cajas actualizadas: {resultado_recalculo.get('cajas_actualizadas')}. "
                                f"Total nuevo: {money(resultado_recalculo.get('total_nuevo'))}."
                            )
                            st.rerun()
                else:
                    st.warning("Solo un administrador puede recalcular precios de pedidos ya guardados.")


                if st.button("Guardar cambios del pedido", key=f"guardar_pedido_edit_{p['id']}"):
                    cambia_precio_o_tipo = recalcular_precios or tipo_edit != (p.get("tipo_cliente") or "Minorista")

                    if cambia_precio_o_tipo and not es_admin:
                        st.error("Esta modificación necesita autorización de un administrador.")
                        return

                    antes_admin = {
                        "cliente_id": p.get("cliente_id"),
                        "cliente_nombre": p.get("cliente_nombre"),
                        "tipo_cliente": p.get("tipo_cliente"),
                        "estado": p.get("estado"),
                        "forma_pago": p.get("forma_pago"),
                        "tipo_cobro": p.get("tipo_cobro"),
                        "observaciones": p.get("observaciones"),
                        "total": p.get("total"),
                    }

                    _actualizar_pedido_admin(
                        db,
                        p["id"],
                        cliente_id_edit,
                        cliente_nombre_edit.strip(),
                        tipo_edit,
                        nuevo_estado,
                        forma_pago_edit,
                        tipo_cobro_edit,
                        obs_edit,
                    )

                    if recalcular_precios:
                        resultado_recalculo = _recalcular_pedido_sql(db, p["id"], tipo_edit)

                        if resultado_recalculo is None:
                            return

                        total_nuevo = _float(resultado_recalculo.get("total_nuevo"))
                        cambios = []
                        sin_producto = []
                        cajas_actualizadas = int(resultado_recalculo.get("cajas_actualizadas") or 0)
                        items_modificados = int(resultado_recalculo.get("items_modificados") or 0)

                        st.session_state[f"recalculo_msg_{p['id']}"] = (
                            f"Recalculado por SQL: {items_modificados} ítems modificados. "
                            f"Cajas actualizadas: {cajas_actualizadas}. "
                            f"Total nuevo: {money(total_nuevo)}."
                        )
                    else:
                        total_nuevo, cambios = _float(p.get("total")), []
                        sin_producto = []
                        cajas_actualizadas = 0

                    _registrar_auditoria_pedido(
                        db,
                        p["id"],
                        "Editar datos del pedido",
                        antes_admin,
                        {
                            "cliente_id": cliente_id_edit,
                            "cliente_nombre": cliente_nombre_edit.strip(),
                            "tipo_cliente": tipo_edit,
                            "estado": nuevo_estado,
                            "forma_pago": forma_pago_edit,
                            "tipo_cobro": tipo_cobro_edit,
                            "observaciones": obs_edit,
                            "total": total_nuevo,
                            "recalculo_precios": recalcular_precios,
                            "cambios_precios": cambios,
                        },
                    )

                    st.success("Pedido actualizado.")
                    st.rerun()

            items_pedido = (
                db.table(table("pedido_detalles"))
                .select("producto_nombre,cantidad,precio_unitario,subtotal,promo_flexible_nombre,promo_combinada_nombre")
                .eq("pedido_id", p["id"])
                .execute()
                .data
            )

            if items_pedido:
                st.dataframe(pd.DataFrame(items_pedido), use_container_width=True, hide_index=True)

            # Ver detalle elegido dentro de promos flexibles/combinadas si existe
            try:
                flex_det = (
                    db.table("namnam_pedido_promo_flexible_items")
                    .select("producto_nombre,cantidad")
                    .eq("pedido_id", p["id"])
                    .execute()
                    .data
                    or []
                )
                combo_det = (
                    db.table("namnam_pedido_promo_combinada_items")
                    .select("familia,producto_nombre,cantidad")
                    .eq("pedido_id", p["id"])
                    .execute()
                    .data
                    or []
                )

                if flex_det or combo_det:
                    with st.expander("Ver composición de promos"):
                        if flex_det:
                            st.markdown("**Promos flexibles**")
                            st.dataframe(pd.DataFrame(flex_det), use_container_width=True, hide_index=True)
                        if combo_det:
                            st.markdown("**Promos combinadas**")
                            st.dataframe(pd.DataFrame(combo_det), use_container_width=True, hide_index=True)
            except Exception:
                pass

            try:
                auditoria = (
                    db.table("namnam_pedidos_auditoria")
                    .select("fecha,usuario,accion")
                    .eq("pedido_id", p["id"])
                    .order("fecha")
                    .execute()
                    .data
                    or []
                )

                if auditoria:
                    with st.expander("🕵️ Historial de modificaciones"):
                        st.dataframe(pd.DataFrame(auditoria), use_container_width=True, hide_index=True)
            except Exception:
                pass

            if p.get("observaciones"):
                st.caption(p["observaciones"])
