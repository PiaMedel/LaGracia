"""
Motor de ventas (sección 10). Registrar una venta = una sola acción que
además descuenta stock automáticamente (sección 32).
"""
from datetime import date
from extensions import db
from models.sales import Sale
from services.inventory_engine import registrar_movimiento, stock_target


def register_sale(product_id, cantidad, precio, canal="Venta directa",
                   customer_id=None, order_id=None, fecha=None, commit=True):
    sale = Sale(
        product_id=product_id,
        cantidad=cantidad,
        precio=precio,
        canal=canal,
        customer_id=customer_id,
        order_id=order_id,
        fecha=fecha or date.today(),
    )
    db.session.add(sale)
    db.session.flush()

    # Si el producto es una fracción (ej. trozo), el stock se descuenta del producto base
    # en la proporción que corresponda (1 trozo = 1/8 de torta). La venta queda a nombre del trozo.
    target, factor = stock_target(product_id)
    registrar_movimiento(
        "product", target, -abs(cantidad) * factor, "venta",
        referencia_tipo="sale", referencia_id=sale.id,
        nota=(f"venta de {abs(cantidad):g} unidad(es) a nombre de otro producto que comparte este stock" if target != product_id else None),
        fecha=fecha, commit=False,
    )
    if commit:
        db.session.commit()
    else:
        db.session.flush()

    # si esta venta viene de un cliente B2B, actualizamos su historial
    if customer_id:
        from models.customers import Customer
        c = Customer.query.get(customer_id)
        if c:
            if c.ultimo_pedido is None or sale.fecha >= c.ultimo_pedido:
                c.ultimo_pedido = sale.fecha
            c.proximo_seguimiento = None  # se recalcula por frecuencia
            if commit:
                db.session.commit()

    return sale
