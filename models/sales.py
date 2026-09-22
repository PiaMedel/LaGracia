from datetime import datetime
from extensions import db

CANALES_VENTA = [
    "Venta directa", "Web", "Instagram", "Cafetería", "Hotel", "Tienda", "Otro B2B",
]


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)
    precio = db.Column(db.Float, nullable=False)
    canal = db.Column(db.String(30), default="Venta directa")
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)  # si viene de un pedido

    customer = db.relationship("Customer")
    product = db.relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "customer_id": self.customer_id,
            "cliente": self.customer.nombre if self.customer else None,
            "product_id": self.product_id,
            "producto": self.product.nombre if self.product else None,
            "cantidad": self.cantidad,
            "precio": self.precio,
            "canal": self.canal,
        }
