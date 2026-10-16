"""
Motor de pre-preparaciones (semi-elaborados congelados).

Responde: ¿cuánto debemos pre-preparar (y congelar) para cubrir la
producción de productos finales que la necesitan?

La demanda de una preparación NO viene de ventas directas (no se vende
sola): viene de cuánto la van a consumir los productos finales que la usan
como ingrediente, según la producción sugerida de esos productos.
"""
import math
from datetime import date

from flask import current_app
from extensions import db
from models.preparations import Preparation, PreparationProduction
from models.recipes import Recipe, RecipeItem
from models.products import Product
from services.inventory_engine import calculate_preparation_stock, registrar_movimiento, last_entry_date


def calculate_preparation_requirement(horizon_days=None):
    """Cuánta cantidad de cada preparación se necesita para cubrir la
    producción SUGERIDA de todos los productos finales que la usan.
    Devuelve {preparation_id: cantidad_necesaria}."""
    from services.production_engine import suggest_production_all  # import diferido (evita ciclo)

    requerimiento = {}
    sugerencias = suggest_production_all(horizon_days=horizon_days)
    for s in sugerencias:
        cantidad_producir = s["produccion_sugerida"]
        if cantidad_producir <= 0:
            continue
        prod = Product.query.get(s["product_id"])
        recipe = prod.effective_recipe if prod is not None else None
        if not recipe or not recipe.rendimiento:
            continue
        factor = cantidad_producir / recipe.rendimiento
        for item in recipe.items:
            if item.ingredient_type != "preparation":
                continue
            necesidad = item.cantidad * factor
            requerimiento[item.preparation_id] = requerimiento.get(item.preparation_id, 0.0) + necesidad

    return {pid: round(v, 2) for pid, v in requerimiento.items()}


def suggest_preparation_production(preparation_id, horizon_days=None):
    """Cantidad sugerida a pre-preparar, con la misma lógica que la
    producción de un producto final: necesidad proyectada + stock de
    seguridad - stock actual."""
    prep = Preparation.query.get(preparation_id)
    if prep is None:
        raise ValueError(f"Preparación {preparation_id} no existe")

    stock_actual = calculate_preparation_stock(preparation_id)
    necesidad = calculate_preparation_requirement(horizon_days).get(preparation_id, 0.0)
    stock_seguridad = prep.stock_seguridad or 0.0

    sugerida = necesidad + stock_seguridad - stock_actual
    sugerida = max(0.0, sugerida)
    if not prep.activo:
        sugerida = 0.0
    sugerida = math.ceil(sugerida) if sugerida else 0.0

    return {
        "preparation_id": preparation_id,
        "preparacion": prep.nombre,
        "stock_actual": stock_actual,
        "stock_seguridad": stock_seguridad,
        "necesidad_proyectada": round(necesidad, 2),
        "produccion_sugerida": sugerida,
        "alerta_vencimiento": check_expiry_alert(prep),
    }


def suggest_preparation_production_all(horizon_days=None, solo_activas=True):
    query = Preparation.query
    if solo_activas:
        query = query.filter(Preparation.activo.is_(True))
    return [suggest_preparation_production(p.id, horizon_days) for p in query.all()]


def check_expiry_alert(preparation, hoy=None):
    """Estimación SIMPLE (sin lotes) de vencimiento próximo: compara la
    fecha del último ingreso de stock contra la vida útil congelada.
    Esto es una aproximación -- si el stock mezcla lotes de distintas
    fechas, la fecha más reciente puede ocultar stock más antiguo que ya
    debería alertar. Ver informe de debilidades."""
    hoy = hoy or date.today()
    if not preparation.vida_util_congelada_dias:
        return None
    ultima_entrada = last_entry_date("preparation", preparation.id)
    if ultima_entrada is None:
        return None
    dias_transcurridos = (hoy - ultima_entrada).days
    dias_restantes = preparation.vida_util_congelada_dias - dias_transcurridos
    if dias_restantes <= 0:
        return {"nivel": "rojo", "dias_restantes": dias_restantes, "texto": "posiblemente vencida"}
    if dias_restantes <= 7:
        return {"nivel": "amarillo", "dias_restantes": dias_restantes, "texto": f"vence en ~{dias_restantes} días"}
    return None


def execute_preparation_production(preparation_id, cantidad_real, fecha=None):
    """Ejecuta la pre-preparación real: consume materias primas según la
    receta de la preparación y suma stock de la preparación (congelada)."""
    prep = Preparation.query.get(preparation_id)
    if prep is None or prep.recipe is None:
        raise ValueError("La preparación no existe o no tiene receta configurada")

    batch = PreparationProduction(
        fecha=fecha or date.today(),
        preparation_id=preparation_id,
        cantidad_real=cantidad_real,
    )
    db.session.add(batch)
    db.session.flush()

    registrar_movimiento(
        "preparation", preparation_id, cantidad_real, "produccion_entrada",
        referencia_tipo="preparation_production", referencia_id=batch.id,
        fecha=fecha, commit=False,
    )

    factor = cantidad_real / prep.recipe.rendimiento
    for item in prep.recipe.items:
        consumo = -(item.cantidad * factor)
        registrar_movimiento(
            "material", item.raw_material_id, consumo, "produccion_consumo",
            referencia_tipo="preparation_production", referencia_id=batch.id,
            fecha=fecha, commit=False,
        )

    db.session.commit()
    return batch
