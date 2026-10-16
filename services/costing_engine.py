"""
Motor de costos (sección 6 del documento), extendido para soportar
ingredientes polimórficos: una receta de producto puede usar materias
primas directas Y/O preparaciones (semi-elaborados) como ingrediente.

Costo unitario = (suma de cantidad_ingrediente * costo_unitario_ingrediente) / rendimiento
Margen unitario = precio_venta - costo_unitario
Margen %       = margen_unitario / precio_venta * 100
"""


def calculate_preparation_cost(preparation):
    """Costo total de UNA tanda de la receta de una preparación (siempre a
    partir de materias primas)."""
    if preparation is None or preparation.recipe is None:
        return None
    total = 0.0
    for item in preparation.recipe.items:
        costo_mp = item.raw_material.costo_unitario or 0.0
        total += (item.cantidad or 0.0) * costo_mp
    return round(total, 2)


def calculate_preparation_unit_cost(preparation):
    """Costo por unidad (kg/un/etc.) de una preparación."""
    if preparation is None or preparation.recipe is None or not preparation.recipe.rendimiento:
        return None
    costo_total = calculate_preparation_cost(preparation)
    if costo_total is None:
        return None
    return round(costo_total / preparation.recipe.rendimiento, 2)


def calculate_recipe_cost(recipe):
    """Costo total de UNA tanda de la receta de un producto final. Cada
    ingrediente puede ser materia prima o preparación."""
    if recipe is None:
        return 0.0
    total = 0.0
    for item in recipe.items:
        costo_unitario_ingrediente = item.costo_unitario_ingrediente()
        total += (item.cantidad or 0.0) * (costo_unitario_ingrediente or 0.0)
    return round(total, 2)


def calculate_unit_cost(product):
    """Costo unitario de un producto, a partir de su receta (propia o compartida).
    Una fracción (trozo) cuesta el costo del producto base dividido en sus unidades."""
    if getattr(product, "base_id", None) and product.base is not None:
        costo_base = calculate_unit_cost(product.base)
        if costo_base is None or not product.unidades_por_base:
            return None
        return round(costo_base / product.unidades_por_base, 2)
    recipe = product.effective_recipe
    if recipe is None or not recipe.rendimiento:
        return None
    costo_receta = calculate_recipe_cost(recipe)
    return round(costo_receta / recipe.rendimiento, 2)


def calculate_margin(product):
    """Devuelve dict con costo unitario, margen $ y margen % para un producto."""
    costo_unitario = calculate_unit_cost(product)
    if costo_unitario is None:
        return {
            "costo_unitario": None,
            "margen_unitario": None,
            "margen_pct": None,
        }
    margen_unitario = round((product.precio_venta or 0.0) - costo_unitario, 2)
    margen_pct = (
        round((margen_unitario / product.precio_venta) * 100, 1)
        if product.precio_venta
        else None
    )
    return {
        "costo_unitario": costo_unitario,
        "margen_unitario": margen_unitario,
        "margen_pct": margen_pct,
    }
