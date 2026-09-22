"""
Motor de diagnóstico de portafolio (sección 24 del documento).

Clasifica productos usando ventas, margen y merma. Es intencionalmente
simple (reglas, no ML) — sirve de base para decisiones de portafolio,
NO decide solo. La clasificación es una SUGERENCIA; el estado real del
producto (el que usa el motor de producción) lo decide el usuario en el
módulo de Productos.
"""
from datetime import date, timedelta
from flask import current_app
from extensions import db
from models.products import Product
from models.sales import Sale
from services.costing_engine import calculate_margin
from services.waste_engine import calculate_waste_pct


def _total_vendido(product_id, window_days):
    since = date.today() - timedelta(days=window_days)
    total = (
        db.session.query(db.func.coalesce(db.func.sum(Sale.cantidad), 0.0))
        .filter(Sale.product_id == product_id, Sale.fecha >= since)
        .scalar()
    )
    return float(total or 0.0)


def classify_all_products(window_days=None):
    """Clasifica todos los productos activos. Usa terciles de ventas relativos
    al resto del catálogo (así "alta/baja" se ajusta solo, sin números mágicos
    fijos que no tendrían sentido para una pastelería chica vs una grande)."""
    window_days = window_days or current_app.config["VENTANA_HISTORICA_DIAS"]
    umbral_merma = current_app.config["UMBRAL_MERMA_ALERTA_PCT"]

    products = Product.query.filter_by(activo=True).all()
    if not products:
        return []

    datos = []
    for p in products:
        ventas = _total_vendido(p.id, window_days)
        margen_info = calculate_margin(p)
        merma_info = calculate_waste_pct(p.id, window_days)
        datos.append({
            "product": p,
            "ventas": ventas,
            "margen_pct": margen_info["margen_pct"],
            "merma_pct": merma_info["merma_pct"],
        })

    ventas_ordenadas = sorted(d["ventas"] for d in datos)
    n = len(ventas_ordenadas)

    def tercil(valor):
        if n < 3:
            # con pocos productos, comparamos contra la mediana simple
            mediana = ventas_ordenadas[n // 2]
            return "alta" if valor >= mediana else "baja"
        p33 = ventas_ordenadas[n // 3]
        p66 = ventas_ordenadas[(2 * n) // 3]
        if valor >= p66:
            return "alta"
        if valor <= p33:
            return "baja"
        return "media"

    resultados = []
    for d in datos:
        p = d["product"]
        nivel_ventas = tercil(d["ventas"])
        margen_pct = d["margen_pct"]
        merma_pct = d["merma_pct"]

        merma_alta = merma_pct is not None and merma_pct > umbral_merma
        margen_desconocido = margen_pct is None
        margen_bajo = (not margen_desconocido) and margen_pct < 20
        margen_alto = (not margen_desconocido) and margen_pct >= 40

        if margen_desconocido:
            estado_sugerido = "REVISAR"
            razon = "Sin receta o costo configurado: no se puede calcular margen."
        elif d["ventas"] == 0:
            estado_sugerido = "PAUSADO"
            razon = f"Sin ventas en los últimos {window_days} días."
        elif merma_alta:
            estado_sugerido = "REVISAR"
            razon = f"Merma de {merma_pct}% supera el umbral ({umbral_merma}%)."
        elif nivel_ventas == "alta" and margen_alto:
            estado_sugerido = "GANADOR"
            razon = "Ventas altas y buen margen."
        elif margen_alto or nivel_ventas == "alta":
            estado_sugerido = "POTENCIAL"
            razon = "Buen margen o buenas ventas, pero no ambos aún."
        elif margen_bajo and nivel_ventas == "baja":
            estado_sugerido = "REVISAR"
            razon = "Ventas bajas y margen bajo."
        else:
            estado_sugerido = "POTENCIAL"
            razon = "Desempeño intermedio."

        resultados.append({
            "product_id": p.id,
            "producto": p.nombre,
            "estado_actual": p.estado,
            "estado_sugerido": estado_sugerido,
            "coincide": estado_sugerido == p.estado,
            "ventas_periodo": d["ventas"],
            "nivel_ventas": nivel_ventas,
            "margen_pct": margen_pct,
            "merma_pct": merma_pct,
            "razon": razon,
        })

    return resultados
