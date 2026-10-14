"""
Motor de compras (secciones 17, 18, 19, 20 del documento).

Responde: ¿qué debemos comprar y cuándo? No reacciona solo a "stock bajo"
(Regla 6): proyecta producción futura + lead time + seguridad.
"""
from datetime import date, timedelta

from flask import current_app
from extensions import db
from models.raw_materials import RawMaterial
from models.recipes import Recipe, RecipeItem
from models.products import Product
from models.purchases import Purchase
from models.inventory import StockMovement
from services.inventory_engine import calculate_raw_material_stock, registrar_movimiento
from services.production_engine import suggest_production_all


def calculate_material_daily_consumption(material_id, window_days=None):
    """Consumo diario real observado (histórico), a partir de los movimientos
    de tipo 'produccion_consumo'. Sirve de respaldo si RawMaterial.consumo_diario_estimado
    no se ha configurado manualmente."""
    window_days = window_days or current_app.config["VENTANA_HISTORICA_DIAS"]
    since = date.today() - timedelta(days=window_days)
    total_consumido = (
        db.session.query(db.func.coalesce(db.func.sum(StockMovement.cantidad), 0.0))
        .filter(
            StockMovement.item_type == "material",
            StockMovement.item_id == material_id,
            StockMovement.tipo_movimiento == "produccion_consumo",
            StockMovement.fecha >= since,
        )
        .scalar()
    )
    total_consumido = float(total_consumido or 0.0)  # es negativo (salida)
    return abs(total_consumido) / window_days if window_days else 0.0


def calculate_material_requirement(horizon_days=None):
    """Proyecta cuánta materia prima se necesitará para cubrir:
      (a) la producción sugerida de productos finales que usan materia
          prima DIRECTAMENTE en su receta, y
      (b) la pre-preparación sugerida de preparaciones (semi-elaborados)
          que esos mismos productos finales necesitan (cascada de 2 niveles).
    Devuelve {material_id: cantidad_necesaria}."""
    from services.preparation_engine import suggest_preparation_production_all

    horizon_days = horizon_days or current_app.config["HORIZONTE_COMPRAS_DIAS"]
    requerimiento = {}

    # (a) materia prima usada directamente en recetas de productos finales
    sugerencias = suggest_production_all(horizon_days=horizon_days)
    for s in sugerencias:
        cantidad_producir = s["produccion_sugerida"]
        if cantidad_producir <= 0:
            continue
        recipe = Recipe.query.filter_by(product_id=s["product_id"]).first()
        if not recipe or not recipe.rendimiento:
            continue
        factor = cantidad_producir / recipe.rendimiento
        for item in recipe.items:
            if item.ingredient_type != "material":
                continue
            necesidad = item.cantidad * factor
            requerimiento[item.raw_material_id] = requerimiento.get(item.raw_material_id, 0.0) + necesidad

    # (b) materia prima usada en la receta de las preparaciones que hace falta pre-preparar
    for prep_sug in suggest_preparation_production_all(horizon_days=horizon_days):
        cantidad_preparar = prep_sug["produccion_sugerida"]
        if cantidad_preparar <= 0:
            continue
        from models.preparations import Preparation
        prep = Preparation.query.get(prep_sug["preparation_id"])
        if not prep or not prep.recipe or not prep.recipe.rendimiento:
            continue
        factor = cantidad_preparar / prep.recipe.rendimiento
        for item in prep.recipe.items:
            necesidad = item.cantidad * factor
            requerimiento[item.raw_material_id] = requerimiento.get(item.raw_material_id, 0.0) + necesidad

    return {mid: round(v, 2) for mid, v in requerimiento.items()}


def reposicion_point(material: RawMaterial):
    """Punto de reposición (sección 18):
    consumo_diario * dias_reposicion + stock_seguridad"""
    consumo_diario = material.consumo_diario_estimado
    if not consumo_diario:
        consumo_diario = calculate_material_daily_consumption(material.id)
    dias = material.dias_reposicion or 0
    return round(consumo_diario * dias + (material.stock_seguridad or 0.0), 2)


def suggest_purchase(material_id, horizon_days=None):
    material = RawMaterial.query.get(material_id)
    if material is None:
        raise ValueError(f"Materia prima {material_id} no existe")

    horizon_days = horizon_days or current_app.config["HORIZONTE_COMPRAS_DIAS"]
    stock_actual = calculate_raw_material_stock(material_id)
    requerimiento = calculate_material_requirement(horizon_days).get(material_id, 0.0)
    punto_reposicion = reposicion_point(material)

    # Necesidad neta = lo que hace falta para producción proyectada + seguridad - lo que hay
    necesidad_neta = requerimiento + (material.stock_seguridad or 0.0) - stock_actual
    # Señal complementaria: aunque no haya producción proyectada calculada,
    # si el stock cae al/bajo el punto de reposición, igual se alerta (Regla 6:
    # no comprar SOLO por stock bajo, pero el punto de reposición ya incorpora
    # consumo proyectado + lead time, así que es una señal válida y distinta).
    bajo_punto_reposicion = stock_actual <= punto_reposicion

    comprar = 0.0
    if necesidad_neta > 0 or bajo_punto_reposicion:
        comprar = max(necesidad_neta, 0.0)
        if bajo_punto_reposicion:
            # asegura cubrir al menos hasta el punto de reposición
            comprar = max(comprar, punto_reposicion - stock_actual)
        # Regla de compra mínima (sección 19)
        if comprar > 0 and material.compra_minima:
            comprar = max(comprar, material.compra_minima)

    return {
        "raw_material_id": material_id,
        "materia_prima": material.nombre,
        "unidad_medida": material.unidad_medida,
        "stock_actual": stock_actual,
        "necesidad_proyectada": round(requerimiento, 2),
        "stock_seguridad": material.stock_seguridad or 0.0,
        "punto_reposicion": punto_reposicion,
        "bajo_punto_reposicion": bajo_punto_reposicion,
        "compra_minima": material.compra_minima or 0.0,
        "comprar": round(comprar, 2) if comprar else 0.0,
    }


def suggest_purchase_all(horizon_days=None, solo_activos=True):
    query = RawMaterial.query
    if solo_activos:
        query = query.filter(RawMaterial.activo.is_(True))
    resultados = [suggest_purchase(m.id, horizon_days) for m in query.all()]
    # Solo mostramos las que realmente requieren compra, ordenadas por urgencia
    return sorted(
        [r for r in resultados if r["comprar"] > 0 or r["bajo_punto_reposicion"]],
        key=lambda r: r["comprar"],
        reverse=True,
    )


def detect_compra_hormiga(material_id=None):
    """Detecta patrón de 'compra hormiga': muchas compras pequeñas y frecuentes
    (sección 20). No es un juicio de que se está comprando mal, es una señal
    para revisar la planificación de abastecimiento."""
    window_days = current_app.config["VENTANA_COMPRA_HORMIGA_DIAS"]
    min_compras = current_app.config["COMPRA_HORMIGA_MIN_COMPRAS"]
    since = date.today() - timedelta(days=window_days)

    query = db.session.query(
        Purchase.raw_material_id, db.func.count(Purchase.id)
    ).filter(Purchase.fecha >= since)
    if material_id:
        query = query.filter(Purchase.raw_material_id == material_id)
    query = query.group_by(Purchase.raw_material_id)

    alertas = []
    for mid, count in query.all():
        if count >= min_compras:
            material = RawMaterial.query.get(mid)
            alertas.append({
                "raw_material_id": mid,
                "materia_prima": material.nombre if material else None,
                "compras_en_periodo": count,
                "ventana_dias": window_days,
            })
    return alertas


def register_purchase(raw_material_id, cantidad, costo_total=None, proveedor=None, fecha=None, commit=True):
    """Registra una compra real: crea el registro de compra Y el movimiento
    de inventario correspondiente (sección 32: una sola acción, el sistema
    hace el resto)."""
    purchase = Purchase(
        raw_material_id=raw_material_id,
        cantidad=cantidad,
        costo_total=costo_total,
        proveedor=proveedor,
        fecha=fecha or date.today(),
    )
    db.session.add(purchase)
    db.session.flush()

    registrar_movimiento(
        "material", raw_material_id, cantidad, "compra",
        referencia_tipo="purchase", referencia_id=purchase.id,
        fecha=fecha, commit=False,
    )
    if commit:
        db.session.commit()
    return purchase
