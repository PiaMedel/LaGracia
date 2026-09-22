from datetime import datetime
from extensions import db

# Regla fundamental (sección 8 del documento):
# El stock NUNCA se modifica directamente. Siempre se calcula como la suma
# de sus movimientos. Esta tabla es la única fuente de verdad del inventario,
# tanto para productos terminados como para materias primas.

TIPOS_MOVIMIENTO = [
    "stock_inicial",
    "compra",
    "produccion_entrada",   # +producto terminado
    "produccion_consumo",   # -materia prima
    "venta",                # -producto terminado
    "merma",                # -producto o -materia prima
    "ajuste",                # +/- corrección manual autorizada
]

ITEM_TYPES = ["product", "material", "preparation"]


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    item_type = db.Column(db.String(10), nullable=False)  # 'product' | 'material'
    item_id = db.Column(db.Integer, nullable=False)  # id de Product o RawMaterial
    cantidad = db.Column(db.Float, nullable=False)  # positivo = entrada, negativo = salida
    tipo_movimiento = db.Column(db.String(30), nullable=False)
    referencia_tipo = db.Column(db.String(30))  # 'sale' | 'production' | 'waste' | 'purchase' | 'manual'
    referencia_id = db.Column(db.Integer)
    nota = db.Column(db.String(255))

    def to_dict(self):
        return {
            "id": self.id,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "item_type": self.item_type,
            "item_id": self.item_id,
            "cantidad": self.cantidad,
            "tipo_movimiento": self.tipo_movimiento,
            "referencia_tipo": self.referencia_tipo,
            "referencia_id": self.referencia_id,
            "nota": self.nota,
        }
