from datetime import datetime
from extensions import db


class Production(db.Model):
    """Registro de una tanda de producción real (o planificada)."""
    __tablename__ = "production"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=datetime.utcnow)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    cantidad_sugerida = db.Column(db.Float)
    cantidad_planificada = db.Column(db.Float)
    cantidad_real = db.Column(db.Float)
    motivo_modificacion = db.Column(db.String(255))
    estado = db.Column(db.String(20), default="planificada")  # planificada / realizada

    product = db.relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "product_id": self.product_id,
            "producto": self.product.nombre if self.product else None,
            "cantidad_sugerida": self.cantidad_sugerida,
            "cantidad_planificada": self.cantidad_planificada,
            "cantidad_real": self.cantidad_real,
            "motivo_modificacion": self.motivo_modificacion,
            "estado": self.estado,
        }
