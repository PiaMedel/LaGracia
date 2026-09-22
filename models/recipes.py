from extensions import db


class Recipe(db.Model):
    __tablename__ = "recipes"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, unique=True)
    rendimiento = db.Column(db.Float, nullable=False, default=1.0)  # unidades que produce la receta

    product = db.relationship("Product", back_populates="recipe")
    items = db.relationship("RecipeItem", back_populates="recipe", cascade="all, delete-orphan")


class RecipeItem(db.Model):
    """Un ingrediente de la receta de un producto final.

    Puede ser una MATERIA PRIMA directa o una PREPARACIÓN (semi-elaborado
    congelado) -- se distingue con `ingredient_type`. Exactamente uno de
    `raw_material_id` / `preparation_id` debe estar seteado.
    """
    __tablename__ = "recipe_items"

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False)
    ingredient_type = db.Column(db.String(15), nullable=False, default="material")  # 'material' | 'preparation'
    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=True)
    preparation_id = db.Column(db.Integer, db.ForeignKey("preparations.id"), nullable=True)
    cantidad = db.Column(db.Float, nullable=False)  # cantidad por 1 tanda (= rendimiento) de receta

    recipe = db.relationship("Recipe", back_populates="items")
    raw_material = db.relationship("RawMaterial")
    preparation = db.relationship("Preparation")

    @property
    def ingredient_name(self):
        if self.ingredient_type == "preparation" and self.preparation:
            return self.preparation.nombre
        if self.raw_material:
            return self.raw_material.nombre
        return "?"

    @property
    def unidad_medida(self):
        if self.ingredient_type == "preparation" and self.preparation:
            return self.preparation.unidad_medida
        if self.raw_material:
            return self.raw_material.unidad_medida
        return ""

    def costo_unitario_ingrediente(self):
        """Costo por unidad del ingrediente (import diferido para evitar
        ciclo de imports con services.costing_engine)."""
        if self.ingredient_type == "preparation":
            from services.costing_engine import calculate_preparation_unit_cost
            return calculate_preparation_unit_cost(self.preparation) or 0.0
        return (self.raw_material.costo_unitario or 0.0) if self.raw_material else 0.0
