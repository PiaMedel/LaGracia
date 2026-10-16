"""
Vínculo "comparte stock con otro producto":

  - "Torta Retail": base = Torta, unidades_por_base = 1  -> mismo stock, ventas y precio propios.
  - "Trozo de torta": base = Torta, unidades_por_base = 8 -> 8 trozos = 1 torta del stock.

Una sola función valida y aplica, para que el formulario y el Excel se comporten igual.
"""
from extensions import db
from models.inventory import StockMovement
from models.products import Product


def apply_links(product, base=None, unidades=None):
    """Valida y asigna el vínculo. Devuelve un mensaje de error (str) o None si quedó bien.
    `product` debe tener id (hacer flush antes si es nuevo). base=None quita el vínculo."""
    nombre = product.nombre
    if base is None:
        product.base_id = None
        product.unidades_por_base = None
        return None

    if base.id == product.id:
        return f"'{nombre}' no puede compartir el stock consigo mismo."
    if base.base_id:
        return (f"'{base.nombre}' ya comparte el stock de otro producto. "
                f"Elige el producto original ('{base.base.nombre}').")
    if not unidades or unidades <= 0:
        return (f"'{nombre}': indica cuántas unidades de este producto equivalen a 1 '{base.nombre}' "
                f"(número mayor que 0; por ejemplo 1 si es lo mismo, u 8 si son trozos).")
    if Product.query.filter(Product.base_id == product.id).count():
        return f"Otros productos comparten el stock de '{nombre}': no puede depender de otro producto."
    if product.base_id != base.id:
        saldo = db.session.query(db.func.coalesce(db.func.sum(StockMovement.cantidad), 0.0)).filter(
            StockMovement.item_type == "product", StockMovement.item_id == product.id).scalar() or 0.0
        if abs(saldo) > 1e-9:
            return (f"'{nombre}' tiene stock propio ({saldo:g}). Déjalo en 0 con 'Conteo' antes de "
                    f"hacer que comparta el stock de '{base.nombre}'.")

    # si tenía receta propia, se descarta: usará la del producto base
    if product.recipe is not None:
        db.session.delete(product.recipe)
        product.recipe = None
    product.base_id = base.id
    product.unidades_por_base = float(unidades)
    return None
