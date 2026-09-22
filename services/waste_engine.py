"""
Motor de mermas (sección 21 del documento).
"""
from datetime import date, timedelta
from flask import current_app
from extensions import db
from models.waste import Waste
from models.production import Production
from services.inventory_engine import registrar_movimiento


def register_waste(item_type, cantidad, motivo, product_id=None, raw_material_id=None, fecha=None):
    if item_type not in ("product", "material"):
        raise ValueError("item_type debe ser 'product' o 'material'")

    waste = Waste(
        item_type=item_type,
        product_id=product_id if item_type == "product" else None,
        raw_material_id=raw_material_id if item_type == "material" else None,
        cantidad=cantidad,
        motivo=motivo,
        fecha=fecha or date.today(),
    )
    db.session.add(waste)
    db.session.flush()

    registrar_movimiento(
        item_type,
        product_id if item_type == "product" else raw_material_id,
        -abs(cantidad),
        "merma",
        referencia_tipo="waste",
        referencia_id=waste.id,
        fecha=fecha,
        commit=False,
    )
    db.session.commit()
    return waste


def calculate_waste_pct(product_id, window_days=None):
    """Merma % = cantidad merma / cantidad producida * 100, para un producto,
    en la ventana histórica indicada."""
    window_days = window_days or current_app.config["VENTANA_HISTORICA_DIAS"]
    since = date.today() - timedelta(days=window_days)

    total_merma = (
        db.session.query(db.func.coalesce(db.func.sum(Waste.cantidad), 0.0))
        .filter(Waste.item_type == "product", Waste.product_id == product_id, Waste.fecha >= since)
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
