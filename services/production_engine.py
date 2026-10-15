"""
Motor de producción (secciones 14, 15, 16 del documento).

Responde: ¿qué debemos producir y cuánto?

Distingue explícitamente (sección 14):
  - demanda CONFIRMADA  (pedidos con estado='Confirmado')
  - demanda PROBABLE    (clientes B2B recurrentes cuyo próximo pedido cae
                         dentro del horizonte, según su frecuencia histórica)
  - demanda NO CONFIRMADA se descarta explícitamente: nunca se usa "quizás
    se venda" para producir.

NOTA DE DISEÑO / INCONSISTENCIA DETECTADA EN EL DOCUMENTO ORIGINAL:
La fórmula de la sección 15 sugiere:
    producción sugerida = demanda esperada + pedidos confirmados
                           + stock seguridad - stock actual
...pero el ejemplo de la sección 4 (mismos números) da un resultado que
excluye el stock de seguridad. Implementamos la fórmula de la sección 15
(la más explícita) y la hacemos configurable vía
Config.INCLUIR_STOCK_SEGURIDAD_EN_SUGERENCIA para que Pía pueda decidir
cuál comportamiento quiere. Ver informe de debilidades.
"""
import math
from datetime import date, timedelta

from flask import current_app
from extensions import db
from models.products import Product
from models.orders import Order, OrderItem
from models.customers import Customer
from models.sales import Sale
from models.production import Production
from services.inventory_engine import calculate_product_stock, registrar_movimiento


def _historical_daily_average(product_id, window_days=None):
    """Venta promedio diaria histórica de un producto (línea base de demanda)."""
    window_days = window_days or current_app.config["VENTANA_HISTORICA_DIAS"]
    since = date.today() - timedelta(days=window_days)
    total = (
        db.session.query(db.func.coalesce(db.func.sum(Sale.cantidad), 0.0))
        .filter(Sale.product_id == product_id, Sale.fecha >= since)
        .scalar()
    )
    return float(total or 0.0) / window_days if window_days else 0.0


def calculate_demand(product_id, horizon_days=None):
    """Calcula demanda confirmada, probable y esperada para un producto,
    dentro del horizonte indicado (por defecto Config.HORIZONTE_DEMANDA_DIAS)."""
    horizon_days = horizon_days or current_app.config["HORIZONTE_DEMANDA_DIAS"]
    today = date.today()
    end = today + timedelta(days=horizon_days)

    # --- Demanda CONFIRMADA: pedidos confirmados con entrega en el horizonte ---
    confirmada = (
        db.session.query(db.func.coalesce(db.func.sum(OrderItem.cantidad), 0.0))
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            OrderItem.product_id == product_id,
            Order.estado == "Confirmado",
            Order.fecha_entrega >= today,
            Order.fecha_entrega <= end,
        )
        .scalar()
    )
    confirmada = float(confirmada or 0.0)

    # --- Demanda PROBABLE: clientes B2B recurrentes cuyo próximo pedido cae en el horizonte ---
    probable = 0.0
    clientes = Customer.query.filter(
        Customer.producto_habitual_id == product_id,
        Customer.frecuencia_habitual_dias.isnot(None),
        Customer.ultimo_pedido.isnot(None),
        Customer.estado == "Activo",
    ).all()
    for c in clientes:
        proximo = c.ultimo_pedido + timedelta(days=c.frecuencia_habitual_dias)
        if today <= proximo <= end:
            probable += float(c.cantidad_promedio or 0.0)

    # --- Línea base histórica (por si no hay señales B2B ni pedidos) ---
    baseline = _historical_daily_average(product_id) * horizon_days

    # Tomamos el mayor entre la proyección histórica general y la demanda
    # probable específica de B2B, para no subestimar ninguna de las dos señales.
    demanda_esperada = max(baseline, probable)

    return {
        "horizon_days": horizon_days,
        "confirmada": round(confirmada, 2),
        "probable": round(probable, 2),
        "baseline_historico": round(baseline, 2),
        "demanda_esperada": round(demanda_esperada, 2),
    }


def suggest_production(product_id, horizon_days=None):
    """Producción sugerida para un producto (Regla 5: nunca sugiere producir
    productos PAUSADOS)."""
    product = Product.query.get(product_id)
    if product is None:
        raise ValueError(f"Producto {product_id} no existe")

    demanda = calculate_demand(product_id, horizon_days)
    stock_actual = calculate_product_stock(product_id)
    stock_seguridad = product.stock_seguridad or 0.0

    if product.estado == "PAUSADO":
        sugerida = 0.0
    else:
        seguridad_term = (
            stock_seguridad
            if current_app.config.get("INCLUIR_STOCK_SEGURIDAD_EN_SUGERENCIA", True)
            else 0.0
        )
        sugerida = (
            demanda["demanda_esperada"] + demanda["confirmada"] + seguridad_term - stock_actual
        )
        sugerida = max(0.0, sugerida)
        sugerida = math.ceil(sugerida)  # no se produce "media unidad"

    return {
        "product_id": product_id,
        "producto": product.nombre,
        "estado_producto": product.estado,
        "stock_actual": stock_actual,
        "stock_seguridad": stock_seguridad,
        "demanda": demanda,
        "produccion_sugerida": sugerida,
    }


def suggest_production_all(horizon_days=None, solo_activos=True):
    query = Product.query
    if solo_activos:
        query = query.filter(Product.activo.is_(True))
    return [suggest_production(p.id, horizon_days) for p in query.all()]


def plan_production(product_id, cantidad_planificada, cantidad_sugerida=None, motivo_modificacion=None):
    """Registra la decisión de producción PLANIFICADA (aún no ejecutada).
    Regla 7/8: el usuario puede cambiar la sugerencia, pero queda registrado."""
    prod = Production(
        product_id=product_id,
        cantidad_sugerida=cantidad_sugerida,
        cantidad_planificada=cantidad_planificada,
        estado="planificada",
        motivo_modificacion=motivo_modificacion,
    )
    db.session.add(prod)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return prod


def execute_production(production_id=None, product_id=None, cantidad_real=None, fecha=None, commit=True):
    """Ejecuta una producción REAL: genera automáticamente los movimientos de
    inventario (sección 32 — mínimos clics, el sistema hace el resto):
      +cantidad_real de producto terminado
      -ingredientes de la receta, proporcional a cantidad_real / rendimiento
    Puede partir de una Production planificada (production_id) o registrarse
    directa (product_id + cantidad_real), sin planificación previa.
    """
    from models.recipes import Recipe

    if production_id:
        prod = Production.query.get(production_id)
        if prod is None:
            raise ValueError("Producción planificada no encontrada")
        product_id = prod.product_id
        cantidad_real = cantidad_real if cantidad_real is not None else prod.cantidad_planificada
        prod.cantidad_real = cantidad_real
        prod.estado = "realizada"
    else:
        if product_id is None or cantidad_real is None:
            raise ValueError("Se requiere product_id y cantidad_real")
        prod = Production(
            product_id=product_id,
            cantidad_planificada=cantidad_real,
            cantidad_real=cantidad_real,
            estado="realizada",
            fecha=(fecha.date() if hasattr(fecha, "hour") else fecha) or date.today(),
        )
        db.session.add(prod)

    db.session.flush()  # asegura prod.id disponible

    # 1) Entrada de producto terminado
    registrar_movimiento(
        "product", product_id, cantidad_real, "produccion_entrada",
        referencia_tipo="production", referencia_id=prod.id,
        fecha=fecha, commit=False,
    )

    # 2) Consumo de ingredientes según receta (materia prima Y/O preparaciones)
    recipe = Recipe.query.filter_by(product_id=product_id).first()
    if recipe and recipe.rendimiento:
        factor = cantidad_real / recipe.rendimiento
        for item in recipe.items:
            consumo = -(item.cantidad * factor)
            if item.ingredient_type == "preparation":
                registrar_movimiento(
                    "preparation", item.preparation_id, consumo, "produccion_consumo",
                    referencia_tipo="production", referencia_id=prod.id,
                    fecha=fecha, commit=False,
                )
            else:
                registrar_movimiento(
                    "material", item.raw_material_id, consumo, "produccion_consumo",
                    referencia_tipo="production", referencia_id=prod.id,
                    fecha=fecha, commit=False,
                )

    db.session.commit()
    return prod
