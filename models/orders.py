from datetime import datetime
from extensions import db

TIPOS_PEDIDO = ["Venta", "Pedido anticipado", "Pedido B2B"]
ESTADOS_PEDIDO = ["Pendiente", "Confirmado", "Producido", "Entregado", "Cancelado"]


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(30), default="Pedido B2B")
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    fecha_pedido = db.Column(db.Date, default=datetime.utcnow)
    fecha_entrega = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(20), default="Pendiente")
    notas = db.Column(db.String(255))

    customer = db.relationship("Customer")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "tipo": self.tipo,
            "customer_id": self.customer_id,
            "cliente": self.customer.nombre if self.customer else None,
            "fecha_pedido": self.fecha_pedido.isoformat() if self.fecha_pedido else None,
            "fecha_entrega": self.fecha_entrega.isoformat() if self.fecha_entrega else None,
            "estado": self.estado,
            "items": [i.to_dict() for i in self.items],
        }


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)
    precio = db.Column(db.Float)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "producto": self.product.nombre if self.product else None,
            "cantidad": self.cantidad,
            "precio": self.precio,
        }
