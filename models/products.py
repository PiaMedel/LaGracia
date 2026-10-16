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

    # COMPARTE STOCK con otro producto (el "base"). Cada producto conserva sus propias ventas y precio,
    # pero el stock y la receta son los del producto base:
    #   "Torta Retail": base = Torta, unidades_por_base = 1   (1 torta retail = 1 torta del stock)
    #   "Trozo de torta": base = Torta, unidades_por_base = 8 (8 trozos = 1 torta; 1 trozo = 1/8)
    # No se produce por separado (se produce el base) ni tiene receta o stock propios.
    base_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    unidades_por_base = db.Column(db.Float, nullable=True)   # ej. 8 (trozos por torta)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    # relaciones
    recipe = db.relationship("Recipe", back_populates="product", uselist=False)
    base = db.relationship("Product", foreign_keys=[base_id], remote_side=[id])

    @property
    def es_fraccion(self):
        return self.base_id is not None

    @property
    def effective_recipe(self):
        """Receta que realmente se usa: la propia, o la de su producto base."""
        if self.recipe is not None and self.recipe.items:
            return self.recipe
        if self.base is not None and self.base.recipe is not None:
            return self.base.recipe          # comparte la receta de su producto base
        return self.recipe

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
            "base_id": self.base_id,
            "unidades_por_base": self.unidades_por_base,
        }
