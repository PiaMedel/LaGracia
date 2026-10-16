"""
Motor de mermas (sección 21 del documento).
"""
from datetime import date, timedelta
from flask import current_app
from extensions import db
from models.waste import Waste
from models.production import Production
from services.inventory_engine import registrar_movimiento, stock_target


def register_waste(item_type, cantidad, motivo, product_id=None, raw_material_id=None, fecha=None,
                   tipo="Merma", nota=None, commit=True):
    """Registra una salida sin venta: MERMA, REGALO o MUESTRA. Descuenta stock.
    Regalos y muestras solo aplican a productos terminados."""
    from models.waste import TIPOS_SALIDA
    if item_type not in ("product", "material"):
        raise ValueError("item_type debe ser 'product' o 'material'")
    if tipo not in TIPOS_SALIDA:
        raise ValueError(f"tipo debe ser uno de {', '.join(TIPOS_SALIDA)}")
    if tipo != "Merma" and item_type != "product":
        raise ValueError("Los regalos y muestras solo se pueden registrar para productos")

    waste = Waste(
        item_type=item_type,
        product_id=product_id if item_type == "product" else None,
        raw_material_id=raw_material_id if item_type == "material" else None,
        cantidad=cantidad,
        motivo=(motivo or ("Otro" if tipo == "Merma" else tipo))[:30],
        tipo=tipo,
        nota=(nota or None) and str(nota)[:255],
        fecha=fecha or date.today(),
    )
    db.session.add(waste)
    db.session.flush()

    if item_type == "product":
        target, factor = stock_target(product_id)     # trozo -> descuenta de la torta base
    else:
        target, factor = raw_material_id, 1.0
    registrar_movimiento(
        item_type,
        target,
        -abs(cantidad) * factor,
        tipo.lower(),                      # 'merma' | 'regalo' | 'muestra'
        referencia_tipo="waste",
        referencia_id=waste.id,
        fecha=fecha,
        commit=False,
    )
    if commit:
        db.session.commit()
    return waste


def waste_summary(window_days=30):
    """Resumen por tipo (últimos N días): cantidad de registros y costo estimado.
    Costo: producto = costo unitario de su receta; materia prima = su costo unitario.
    (Las unidades no se suman entre ítems porque cada uno tiene su propia unidad.)"""
    from models.waste import TIPOS_SALIDA
    from services.costing_engine import calculate_unit_cost
    since = date.today() - timedelta(days=window_days)
    out = {t: {"registros": 0, "costo": 0.0} for t in TIPOS_SALIDA}
    for w in Waste.query.filter(Waste.fecha >= since).all():
        t = w.tipo or "Merma"
        if t not in out:
            continue
        if w.item_type == "product" and w.product is not None:
            unit = calculate_unit_cost(w.product) or 0.0
        elif w.raw_material is not None:
            unit = w.raw_material.costo_unitario or 0.0
        else:
            unit = 0.0
        out[t]["registros"] += 1
        out[t]["costo"] += unit * (w.cantidad or 0.0)
    return out


def calculate_waste_pct(product_id, window_days=None):
    """Merma % = cantidad merma / cantidad producida * 100, para un producto,
    en la ventana histórica indicada. Solo cuentan las MERMAS (no regalos ni muestras)."""
    window_days = window_days or current_app.config["VENTANA_HISTORICA_DIAS"]
    since = date.today() - timedelta(days=window_days)

    total_merma = (
        db.session.query(db.func.coalesce(db.func.sum(Waste.cantidad), 0.0))
        .filter(Waste.item_type == "product", Waste.product_id == product_id, Waste.fecha >= since,
                db.or_(Waste.tipo == "Merma", Waste.tipo.is_(None)))
        .scalar()
    )
    total_producido = (
        db.session.query(db.func.coalesce(db.func.sum(Production.cantidad_real), 0.0))
        .filter(Production.product_id == product_id, Production.fecha >= since)
        .scalar()
    )
    total_merma = float(total_merma or 0.0)
    total_producido = float(total_producido or 0.0)

    pct = (total_merma / total_producido * 100) if total_producido else 0.0
    return {
        "product_id": product_id,
        "total_merma": total_merma,
        "total_producido": total_producido,
        "merma_pct": round(pct, 1),
    }


def calculate_waste_alerts(window_days=None):
    """Productos cuya merma % supera el umbral configurado."""
    from models.products import Product
    umbral = current_app.config["UMBRAL_MERMA_ALERTA_PCT"]
    alertas = []
    for p in Product.query.filter_by(activo=True).all():
        info = calculate_waste_pct(p.id, window_days)
        if info["merma_pct"] > umbral and info["total_producido"] > 0:
            info["producto"] = p.nombre
            alertas.append(info)
    return alertas
