"""
Motor de ventas (sección 10). Registrar una venta = una sola acción que
además descuenta stock automáticamente (sección 32).
"""
from datetime import date
from extensions import db
from models.sales import Sale
from services.inventory_engine import registrar_movimiento


def register_sale(product_id, cantidad, precio, canal="Venta directa",
                   customer_id=None, order_id=None, fecha=None):
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

    registrar_movimiento(
        "product", product_id, -abs(cantidad), "venta",
        referencia_tipo="sale", referencia_id=sale.id,
        fecha=fecha, commit=False,
    )
    db.session.commit()

    # si esta venta viene de un cliente B2B, actualizamos su historial
    if customer_id:
        from models.customers import Customer
        c = Customer.query.get(customer_id)
        if c:
            c.ultimo_pedido = sale.fecha
            c.proximo_seguimiento = None  # se recalcula por frecuencia
            db.session.commit()

    return sale
