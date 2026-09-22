from extensions import db

# Una PREPARACIÓN es un semi-elaborado (masa, relleno, base, mezcla) que se
# hace con anticipación a partir de materias primas, se congela, y queda
# como inventario propio -- ni materia prima ni producto terminado.
#
# Flujo: Materia prima -> (receta de preparación) -> PREPARACIÓN (congelada)
#        PREPARACIÓN -> (ingrediente de la receta de un producto final) -> Producto terminado
#
# Control de vencimiento SIMPLE (sin lotes individuales): se guardan dos
# duraciones de referencia. La app estima "posible vencimiento" comparando
# la fecha del último movimiento de entrada contra estas duraciones; es una
# aproximación, no un control exacto por lote (ver informe de debilidades).


class Preparation(db.Model):
    __tablename__ = "preparations"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    unidad_medida = db.Column(db.String(20), default="kg")
    stock_seguridad = db.Column(db.Float, default=0.0)
    vida_util_congelada_dias = db.Column(db.Integer)      # ej. 90 días en el congelador
    vida_util_descongelada_dias = db.Column(db.Integer)   # ej. 2 días una vez fuera del congelador
    activo = db.Column(db.Boolean, default=True)

    recipe = db.relationship("PreparationRecipe", back_populates="preparation", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "unidad_medida": self.unidad_medida,
            "stock_seguridad": self.stock_seguridad,
            "vida_util_congelada_dias": self.vida_util_congelada_dias,
            "vida_util_descongelada_dias": self.vida_util_descongelada_dias,
            "activo": self.activo,
        }


class PreparationRecipe(db.Model):
    """Receta de la preparación: SIEMPRE a partir de materias primas."""
    __tablename__ = "preparation_recipes"

    id = db.Column(db.Integer, primary_key=True)
    preparation_id = db.Column(db.Integer, db.ForeignKey("preparations.id"), nullable=False, unique=True)
    rendimiento = db.Column(db.Float, nullable=False, default=1.0)

    preparation = db.relationship("Preparation", back_populates="recipe")
    items = db.relationship("PreparationRecipeItem", back_populates="recipe", cascade="all, delete-orphan")


class PreparationRecipeItem(db.Model):
    __tablename__ = "preparation_recipe_items"

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("preparation_recipes.id"), nullable=False)
    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)

    recipe = db.relationship("PreparationRecipe", back_populates="items")
    raw_material = db.relationship("RawMaterial")


class PreparationProduction(db.Model):
    """Registro de una tanda de pre-preparación (análogo a Production, pero
    para el semi-elaborado)."""
    __tablename__ = "preparation_production"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date)
    preparation_id = db.Column(db.Integer, db.ForeignKey("preparations.id"), nullable=False)
    cantidad_sugerida = db.Column(db.Float)
    cantidad_real = db.Column(db.Float)

    preparation = db.relationship("Preparation")
