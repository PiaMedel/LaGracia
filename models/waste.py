from datetime import datetime
from extensions import db

MOTIVOS_MERMA = ["Vencimiento", "Producción defectuosa", "Daño", "Sobreproducción", "Error", "Otro"]


class Waste(db.Model):
    __tablename__ = "waste"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=datetime.utcnow)
    item_type = db.Column(db.String(10), nullable=False)  # 'product' | 'material'
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=True)
    cantidad = db.Column(db.Float, nullable=False)
    motivo = db.Column(db.String(30), default="Otro")

    product = db.relationship("Product")
    raw_material = db.relationship("RawMaterial")

    def to_dict(self):
        return {
            "id": self.id,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "item_type": self.item_type,
            "producto": self.product.nombre if self.product else None,
            "materia_prima": self.raw_material.nombre if self.raw_material else None,
            "cantidad": self.cantidad,
            "motivo": self.motivo,
        }
