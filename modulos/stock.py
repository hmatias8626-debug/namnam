import pandas as pd
import streamlit as st

from services.db import require_db, fetch_table, table
from services.ui import header


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


def render():
    header("📊 Stock", "Stock separado por familia de producto")
    db = require_db()

    productos = [p for p in fetch_table("productos") if p.get("activo")]
    stock_rows = fetch_table("stock")

    stock_por_producto = {}
    for s in stock_rows:
        stock_por_producto[s.get("producto_id")] = s

    familias = {}
    for p in productos:
        familia = _familia_producto(p)
        familias.setdefault(familia, []).append(p)

    if not productos:
        st.info("Todavía no hay productos activos.")
        return

    familias_ordenadas = _ordenar_familias(familias)

    if "familia_actual_stock" not in st.session_state:
        st.session_state["familia_actual_stock"] = familias_ordenadas[0]

    if st.session_state["familia_actual_stock"] not in familias_ordenadas:
        st.session_state["familia_actual_stock"] = familias_ordenadas[0]

    labels = [f"{_emoji_familia(f)} {f}" for f in familias_ordenadas]
    label_to_family = {f"{_emoji_familia(f)} {f}": f for f in familias_ordenadas}

    current = st.session_state["familia_actual_stock"]
    current_label = f"{_emoji_familia(current)} {current}"
    idx = labels.index(current_label) if current_label in labels else 0

    selected = st.radio(
        "Familia",
        labels,
        index=idx,
        horizontal=True,
        key="radio_familia_stock"
    )

    familia_actual = label_to_family[selected]
    st.session_state["familia_actual_stock"] = familia_actual

    st.markdown(f"### {_emoji_familia(familia_actual)} {familia_actual}")

    productos_familia = familias[familia_actual]

    total_unidades = 0.0
    for p in productos_familia:
        row = stock_por_producto.get(p["id"], {})
        total_unidades += _float(row.get("cantidad"))

    st.metric("Unidades en esta familia", f"{total_unidades:g}")

    st.divider()

    for p in productos_familia:
        stock_actual = _float(stock_por_producto.get(p["id"], {}).get("cantidad"))
        unidad = p.get("unidad") or "unidad"

        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 2, 2])

            c1.markdown(f"### {p.get('nombre')}")
            c1.caption(f"Familia: {familia_actual} · Unidad: {unidad}")

            c2.metric("Stock actual", f"{stock_actual:g}")

            nuevo_stock = c3.number_input(
                "Nuevo stock",
                min_value=0.0,
                step=1.0,
                value=stock_actual,
                key=f"stock_{p['id']}"
            )

            if st.button("Guardar stock", key=f"guardar_stock_{p['id']}"):
                existe = stock_por_producto.get(p["id"])

                if existe:
                    db.table(table("stock")).update({
                        "cantidad": nuevo_stock
                    }).eq("producto_id", p["id"]).execute()
                else:
                    db.table(table("stock")).insert({
                        "producto_id": p["id"],
                        "cantidad": nuevo_stock
                    }).execute()

                st.success("Stock actualizado.")
                st.rerun()

    st.divider()
    st.subheader("Resumen general por familia")

    resumen = []
    for fam in familias_ordenadas:
        total = 0.0
        for p in familias[fam]:
            total += _float(stock_por_producto.get(p["id"], {}).get("cantidad"))
        resumen.append({
            "Familia": f"{_emoji_familia(fam)} {fam}",
            "Unidades": total,
        })

    st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)
