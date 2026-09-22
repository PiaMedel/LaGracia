from extensions import db


class RawMaterial(db.Model):
    __tablename__ = "raw_materials"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    unidad_medida = db.Column(db.String(20), default="kg")  # kg, g, un, l, ml
    stock_seguridad = db.Column(db.Float, default=0.0)
    consumo_diario_estimado = db.Column(db.Float, default=0.0)  # se puede recalcular
    dias_reposicion = db.Column(db.Integer, default=3)
    compra_minima = db.Column(db.Float, default=0.0)
    costo_unitario = db.Column(db.Float, default=0.0)
    proveedor = db.Column(db.String(120))
    vida_util_dias = db.Column(db.Integer)  # control simple de vencimiento (sin lotes)
    activo = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "unidad_medida": self.unidad_medida,
            "stock_seguridad": self.stock_seguridad,
            "consumo_diario_estimado": self.consumo_diario_estimado,
            "dias_reposicion": self.dias_reposicion,
            "compra_minima": self.compra_minima,
            "costo_unitario": self.costo_unitario,
            "proveedor": self.proveedor,
            "vida_util_dias": self.vida_util_dias,
            "activo": self.activo,
        }

