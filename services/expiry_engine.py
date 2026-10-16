"""
Control de vencimiento SIMPLE (sin lotes individuales), aplicable a
materia prima, preparaciones y productos terminados.

Cómo funciona: cada item tiene una "vida útil en días" de referencia.
Se compara contra la fecha del ÚLTIMO movimiento de entrada de stock
(compra / producción / stock inicial).

Limitación conocida (por diseño, ya que se optó por el modo simple):
si el stock actual mezcla unidades de distintas fechas (por ejemplo,
quedan 2 brownies de hace 4 días y se acaban de producir 20 más), la
fecha del último ingreso "tapa" la de las unidades más viejas. El
sistema no puede saber cuáles de las unidades en stock son las viejas.
Sirve como alerta orientativa, no como trazabilidad exacta por lote.
"""
from datetime import date
from services.inventory_engine import last_entry_date


def check_item_expiry(item_type, item_id, vida_util_dias, hoy=None, umbral_alerta_dias=None):
    """Devuelve None si no hay riesgo, o un dict de alerta si el item está
    por vencer o posiblemente vencido, según su última entrada de stock."""
    if not vida_util_dias:
        return None
    hoy = hoy or date.today()
    umbral_alerta_dias = umbral_alerta_dias if umbral_alerta_dias is not None else max(1, round(vida_util_dias * 0.25))

    ultima_entrada = last_entry_date(item_type, item_id)
    if ultima_entrada is None:
        return None

    dias_transcurridos = (hoy - ultima_entrada).days
    dias_restantes = vida_util_dias - dias_transcurridos

    if dias_restantes <= 0:
        return {"nivel": "rojo", "dias_restantes": dias_restantes, "texto": "posiblemente vencido"}
    if dias_restantes <= umbral_alerta_dias:
        return {"nivel": "amarillo", "dias_restantes": dias_restantes, "texto": f"vence en ~{dias_restantes} días"}
    return None


def expiry_alerts_for_materials():
    from models.raw_materials import RawMaterial
    from services.inventory_engine import calculate_raw_material_stock
    alertas = []
    for m in RawMaterial.query.filter_by(activo=True).all():
        if calculate_raw_material_stock(m.id) <= 0:
            continue
        info = check_item_expiry("material", m.id, m.vida_util_dias)
        if info:
            info.update({"tipo": "Materia prima", "nombre": m.nombre})
            alertas.append(info)
    return alertas


def expiry_alerts_for_preparations():
    from models.preparations import Preparation
    from services.inventory_engine import calculate_preparation_stock
    alertas = []
    for p in Preparation.query.filter_by(activo=True).all():
        if calculate_preparation_stock(p.id) <= 0:
            continue
        info = check_item_expiry("preparation", p.id, p.vida_util_congelada_dias)
        if info:
            info.update({"tipo": "Pre-preparación", "nombre": p.nombre})
            alertas.append(info)
    return alertas


def expiry_alerts_for_products():
    from models.products import Product
    from services.inventory_engine import calculate_product_stock
    alertas = []
    for p in Product.query.filter_by(activo=True).all():
        if p.base_id or calculate_product_stock(p.id) <= 0:
            continue
        info = check_item_expiry("product", p.id, p.vida_util_dias)
        if info:
            info.update({"tipo": "Producto", "nombre": p.nombre})
            alertas.append(info)
    return alertas


def all_expiry_alerts():
    alertas = expiry_alerts_for_materials() + expiry_alerts_for_preparations() + expiry_alerts_for_products()
    orden = {"rojo": 0, "amarillo": 1}
    alertas.sort(key=lambda a: (orden.get(a["nivel"], 9), a["dias_restantes"]))
    return alertas
