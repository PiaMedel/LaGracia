from datetime import datetime
from extensions import db


class Purchase(db.Model):
    """Compra real registrada de una materia prima. Genera un StockMovement."""
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=datetime.utcnow)
    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)
    costo_total = db.Column(db.Float)
    proveedor = db.Column(db.String(120))

    raw_material = db.relationship("RawMaterial")

    def to_dict(self):
        return {
            "id": self.id,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "raw_material_id": self.raw_material_id,
            "materia_prima": self.raw_material.nombre if self.raw_material else None,
            "cantidad": self.cantidad,
            "costo_total": self.costo_total,
            "proveedor": self.proveedor,
        }
