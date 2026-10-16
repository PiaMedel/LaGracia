"""
Motor de inventario.

Regla fundamental (Regla 1 del documento): el stock SIEMPRE se obtiene desde
movimientos, nunca se escribe un campo "stock" directo en Product o
RawMaterial. Todas las demás capas (ventas, producción, compras, mermas)
deben llamar a `registrar_movimiento` en vez de tocar cualquier cosa a mano.
"""
from datetime import datetime
from extensions import db
from models.inventory import StockMovement


def registrar_movimiento(item_type, item_id, cantidad, tipo_movimiento,
                          referencia_tipo=None, referencia_id=None, nota=None,
                          fecha=None, commit=True):
    """Crea un movimiento de inventario. cantidad puede ser + o -."""
    if item_type not in ("product", "material", "preparation"):
        raise ValueError("item_type debe ser 'product', 'material' o 'preparation'")

    mov = StockMovement(
        fecha=fecha or datetime.utcnow(),
        item_type=item_type,
        item_id=item_id,
        cantidad=cantidad,
        tipo_movimiento=tipo_movimiento,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        nota=nota,
    )
    db.session.add(mov)
    if commit:
        db.session.commit()
    return mov


def stock_target(product_id):
    """(id del producto que lleva el stock, factor). Un producto normal lleva su propio
    stock (factor 1). Una FRACCIÓN (ej. trozo = 1/8 de torta) descuenta del producto
    base: 1 trozo = 1/8 de torta, o sea factor 1/8."""
    from models.products import Product
    p = db.session.get(Product, product_id)
    if p is not None and p.base_id and p.unidades_por_base:
        return p.base_id, 1.0 / p.unidades_por_base
    return product_id, 1.0


def calculate_product_stock(product_id):
    """Stock actual de un producto terminado = suma de sus movimientos.
    Para una fracción (trozo) es DERIVADO: stock de la torta x trozos por torta."""
    target, factor = stock_target(product_id)
    if target != product_id:
        return calculate_product_stock(target) / factor
    total = (
        db.session.query(db.func.coalesce(db.func.sum(StockMovement.cantidad), 0.0))
        .filter(StockMovement.item_type == "product", StockMovement.item_id == product_id)
        .scalar()
    )
    return float(total or 0.0)


def calculate_raw_material_stock(material_id):
    """Stock actual de una materia prima = suma de sus movimientos."""
    total = (
        db.session.query(db.func.coalesce(db.func.sum(StockMovement.cantidad), 0.0))
        .filter(StockMovement.item_type == "material", StockMovement.item_id == material_id)
        .scalar()
    )
    return float(total or 0.0)


def get_all_product_stocks():
    """Devuelve {product_id: stock} para todos los productos con movimientos."""
    rows = (
        db.session.query(StockMovement.item_id, db.func.sum(StockMovement.cantidad))
        .filter(StockMovement.item_type == "product")
        .group_by(StockMovement.item_id)
        .all()
    )
    stocks = {pid: float(total or 0.0) for pid, total in rows}
    from models.products import Product
    for f in Product.query.filter(Product.base_id.isnot(None)).all():   # fracciones: derivado de la base
        stocks[f.id] = stocks.get(f.base_id, 0.0) * (f.unidades_por_base or 0.0)
    return stocks


def get_all_material_stocks():
    """Devuelve {material_id: stock} para todas las materias primas con movimientos."""
    rows = (
        db.session.query(StockMovement.item_id, db.func.sum(StockMovement.cantidad))
        .filter(StockMovement.item_type == "material")
        .group_by(StockMovement.item_id)
        .all()
    )
    return {mid: float(total or 0.0) for mid, total in rows}


def calculate_preparation_stock(preparation_id):
    """Stock actual de una preparación (semi-elaborado) = suma de sus movimientos."""
    total = (
        db.session.query(db.func.coalesce(db.func.sum(StockMovement.cantidad), 0.0))
        .filter(StockMovement.item_type == "preparation", StockMovement.item_id == preparation_id)
        .scalar()
    )
    return float(total or 0.0)


def get_all_preparation_stocks():
    """Devuelve {preparation_id: stock} para todas las preparaciones con movimientos."""
    rows = (
        db.session.query(StockMovement.item_id, db.func.sum(StockMovement.cantidad))
        .filter(StockMovement.item_type == "preparation")
        .group_by(StockMovement.item_id)
        .all()
    )
    return {pid: float(total or 0.0) for pid, total in rows}


def last_entry_date(item_type, item_id, tipos_entrada=None):
    """Fecha del último movimiento de ENTRADA (compra, producción, stock
    inicial) para un item. Se usa para estimar vencimiento en modo simple
    (sin lotes): es una aproximación, no un control exacto por lote."""
    tipos_entrada = tipos_entrada or ["compra", "produccion_entrada", "stock_inicial", "ajuste"]
    mov = (
        StockMovement.query.filter(
            StockMovement.item_type == item_type,
            StockMovement.item_id == item_id,
            StockMovement.tipo_movimiento.in_(tipos_entrada),
            StockMovement.cantidad > 0,
        )
        .order_by(StockMovement.fecha.desc())
        .first()
    )
    return mov.fecha.date() if mov else None


def movement_history(item_type, item_id, limit=100):
    return (
        StockMovement.query.filter_by(item_type=item_type, item_id=item_id)
        .order_by(StockMovement.fecha.desc())
        .limit(limit)
        .all()
    )


def get_stock(item_type, item_id):
    if item_type == "product":
        return calculate_product_stock(item_id)
    if item_type == "material":
        return calculate_raw_material_stock(item_id)
    if item_type == "preparation":
        return calculate_preparation_stock(item_id)
    raise ValueError("item_type no válido")


def set_stock_to(item_type, item_id, stock_real, nota="Conteo físico", commit=True):
    """Conteo físico: ajusta el stock del sistema al valor realmente contado,
    registrando la DIFERENCIA como un movimiento de tipo 'ajuste' (el historial
    queda intacto y auditable). Devuelve la diferencia aplicada (puede ser 0)."""
    actual = get_stock(item_type, item_id)
    diff = round(stock_real - actual, 6)
    if abs(diff) < 1e-9:
        return 0.0
    registrar_movimiento(item_type, item_id, diff, "ajuste",
                         referencia_tipo="manual", nota=nota, commit=commit)
    return diff
