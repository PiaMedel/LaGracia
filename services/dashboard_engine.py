"""
Compone la pantalla HOY (sección 4) y el dashboard de indicadores (sección 23),
combinando todos los motores. Este módulo NO contiene reglas de negocio propias:
solo orquesta los engines especializados. Así, la lógica de negocio real se
mantiene en un solo lugar por dominio (Regla de arquitectura, sección 27).
"""
from datetime import date, timedelta
from flask import current_app
from extensions import db
from models.products import Product
from models.sales import Sale
from models.customers import Customer
from models.orders import Order

from services.inventory_engine import calculate_product_stock, get_all_product_stocks
from services.production_engine import suggest_production_all
from services.preparation_engine import suggest_preparation_production_all
from services.purchasing_engine import suggest_purchase_all, detect_compra_hormiga
from services.b2b_engine import calculate_b2b_followups
from services.waste_engine import calculate_waste_alerts, calculate_waste_pct
from services.expiry_engine import all_expiry_alerts


def build_alerts():
    """Genera la lista de alertas priorizadas de la pantalla HOY."""
    alertas = []

    # 🔴 Stock crítico de productos (por debajo de su stock de seguridad)
    stocks = get_all_product_stocks()
    for p in Product.query.filter_by(activo=True).all():
        stock = stocks.get(p.id, 0.0)
        if p.stock_seguridad and stock < p.stock_seguridad:
            alertas.append({
                "nivel": "rojo",
                "texto": f"Stock de {p.nombre} bajo ({stock:g} / seguridad {p.stock_seguridad:g}).",
            })

    # 🔴 / 🟡 Materias primas a comprar
    compras = suggest_purchase_all()
    for c in compras:
        nivel = "rojo" if c["bajo_punto_reposicion"] else "amarillo"
        alertas.append({
            "nivel": nivel,
            "texto": f"Comprar {c['materia_prima']}: faltan {c['comprar']:g} {c['unidad_medida']}.",
        })

    # 🟠 Clientes B2B a contactar hoy o atrasados
    for f in calculate_b2b_followups():
        if f["urgencia"] in ("hoy", "atrasado"):
            extra = " (atrasado)" if f["urgencia"] == "atrasado" else ""
            alertas.append({
                "nivel": "naranja",
                "texto": f"{f['cliente']} debería hacer pedido hoy{extra}.",
            })

    # 🟠 Merma sobre el promedio / umbral
    for w in calculate_waste_alerts():
        alertas.append({
            "nivel": "naranja",
            "texto": f"Merma de {w['producto']} ({w['merma_pct']}%) supera el umbral.",
        })

    # 🟡 Compra hormiga
    for h in detect_compra_hormiga():
        alertas.append({
            "nivel": "amarillo",
            "texto": (
                f"Posible compra hormiga de {h['materia_prima']}: "
                f"{h['compras_en_periodo']} compras en {h['ventana_dias']} días."
            ),
        })

    # 🔴 / 🟡 Vencimientos próximos (modo simple, sin lotes)
    for v in all_expiry_alerts():
        nivel = "rojo" if v["nivel"] == "rojo" else "amarillo"
        alertas.append({
            "nivel": nivel,
            "texto": f"{v['tipo']} {v['nombre']}: {v['texto']}.",
        })

    orden = {"rojo": 0, "naranja": 1, "amarillo": 2}
    alertas.sort(key=lambda a: orden.get(a["nivel"], 9))
    return alertas


def build_hoy_dashboard():
    """Arma toda la info de la pantalla HOY en un solo objeto."""
    producto_rows = []
    for s in suggest_production_all():
        producto_rows.append({
            "producto": s["producto"],
            "product_id": s["product_id"],
            "stock": s["stock_actual"],
            "demanda_proxima": s["demanda"]["demanda_esperada"],
            "confirmado": s["demanda"]["confirmada"],
            "sugerencia": s["produccion_sugerida"],
        })

    compras_rows = suggest_purchase_all()
    preparacion_rows = [r for r in suggest_preparation_production_all() if r["produccion_sugerida"] > 0]
    b2b_rows = calculate_b2b_followups()
    alertas = build_alerts()

    total_producir = sum(r["sugerencia"] for r in producto_rows)
    total_comprar = len(compras_rows)
    total_preparar = len(preparacion_rows)
    total_contactar = len([b for b in b2b_rows if b["urgencia"] in ("hoy", "atrasado")])
    stock_critico = len([
        a for a in alertas if a["nivel"] == "rojo" and "Stock de" in a["texto"]
    ])

    # merma % global reciente (todos los productos)
    productos_activos = Product.query.filter_by(activo=True).all()
    merma_total = 0.0
    producido_total = 0.0
    for p in productos_activos:
        info = calculate_waste_pct(p.id)
        merma_total += info["total_merma"]
        producido_total += info["total_producido"]
    merma_pct_global = round((merma_total / producido_total * 100), 1) if producido_total else 0.0

    return {
        "resumen": {
            "producir_unidades": total_producir,
            "comprar_items": total_comprar,
            "preparar_items": total_preparar,
            "contactar_clientes": total_contactar,
            "alertas": len(alertas),
            "stock_critico": stock_critico,
            "merma_pct": merma_pct_global,
        },
        "produccion": producto_rows,
        "compras": compras_rows,
        "preparacion": preparacion_rows,
        "b2b": b2b_rows,
        "alertas": alertas,
    }


def build_indicators_dashboard():
    """Dashboard de indicadores (sección 23)."""
    today = date.today()

    def ventas_en(desde):
        total = (
            db.session.query(db.func.coalesce(db.func.sum(Sale.cantidad * Sale.precio), 0.0))
            .filter(Sale.fecha >= desde)
            .scalar()
        )
        return float(total or 0.0)

    ventas_hoy = ventas_en(today)
    ventas_semana = ventas_en(today - timedelta(days=7))
    ventas_mes = ventas_en(today - timedelta(days=30))

    # más y menos vendidos (por unidades, ventana histórica configurada)
    window = current_app.config["VENTANA_HISTORICA_DIAS"]
    since = today - timedelta(days=window)
    ranking = (
        db.session.query(Sale.product_id, db.func.sum(Sale.cantidad).label("total"))
        .filter(Sale.fecha >= since)
        .group_by(Sale.product_id)
        .order_by(db.desc("total"))
        .all()
    )
    productos = {p.id: p.nombre for p in Product.query.all()}
    mas_vendidos = [{"producto": productos.get(pid, "?"), "cantidad": float(t)} for pid, t in ranking[:5]]
    menos_vendidos = [{"producto": productos.get(pid, "?"), "cantidad": float(t)} for pid, t in ranking[-5:]]

    stocks_productos = get_all_product_stocks()
    productos_bajo_stock = [
        p.nombre for p in Product.query.filter_by(activo=True).all()
        if p.stock_seguridad and stocks_productos.get(p.id, 0.0) < p.stock_seguridad
    ]

    from services.inventory_engine import get_all_material_stocks
    from models.raw_materials import RawMaterial
    stocks_materiales = get_all_material_stocks()
    materiales_bajo_stock = [
        m.nombre for m in RawMaterial.query.filter_by(activo=True).all()
        if m.stock_seguridad and stocks_materiales.get(m.id, 0.0) < m.stock_seguridad
    ]

    clientes_activos = Customer.query.filter_by(estado="Activo").count()
    clientes_inactivos = Customer.query.filter_by(estado="Inactivo").count()
    pedidos_confirmados = Order.query.filter_by(estado="Confirmado").count()
    b2b_por_contactar = len([
        b for b in calculate_b2b_followups() if b["urgencia"] in ("hoy", "atrasado")
    ])

    merma_alertas = calculate_waste_alerts()

    return {
        "ventas": {"hoy": ventas_hoy, "semana": ventas_semana, "mes": ventas_mes},
        "productos": {"mas_vendidos": mas_vendidos, "menos_vendidos": menos_vendidos},
        "inventario": {
            "productos_bajo_stock": productos_bajo_stock,
            "materias_primas_bajo_stock": materiales_bajo_stock,
        },
        "b2b": {
            "clientes_activos": clientes_activos,
            "clientes_inactivos": clientes_inactivos,
            "pedidos_confirmados": pedidos_confirmados,
            "por_contactar": b2b_por_contactar,
        },
        "merma": {
            "productos_con_alerta": len(merma_alertas),
            "detalle": merma_alertas,
        },
    }
