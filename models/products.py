from datetime import datetime
from extensions import db

# Estados válidos de un producto (regla: no todos los productos entran
# automáticamente al plan de producción — sección 5 del documento)
ESTADOS_PRODUCTO = ["GANADOR", "POTENCIAL", "REVISAR", "PAUSADO"]


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    categoria = db.Column(db.String(80))
    unidad_venta = db.Column(db.String(30), default="unidad")
    precio_venta = db.Column(db.Float, nullable=False, default=0.0)
    estado = db.Column(db.String(20), default="POTENCIAL")
    stock_seguridad = db.Column(db.Float, default=0.0)
    vida_util_dias = db.Column(db.Integer)
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    # relaciones
    recipe = db.relationship("Recipe", back_populates="product", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "categoria": self.categoria,
            "unidad_venta": self.unidad_venta,
            "precio_venta": self.precio_venta,
            "estado": self.estado,
            "stock_seguridad": self.stock_seguridad,
            "vida_util_dias": self.vida_util_dias,
            "activo": self.activo,
        }
