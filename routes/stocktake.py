from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from models.products import Product
from models.raw_materials import RawMaterial
from services.inventory_engine import calculate_product_stock, calculate_raw_material_stock, set_stock_to

bp = Blueprint("stocktake", __name__, url_prefix="/conteo")


def _num(txt):
    s = (txt or "").strip().replace(" ", "")
    if s == "":
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    return float(s)


@bp.route("/", methods=["GET", "POST"])
def conteo():
    productos = Product.query.filter_by(activo=True).order_by(Product.nombre).all()
    materiales = RawMaterial.query.filter_by(activo=True).order_by(RawMaterial.nombre).all()

    if request.method == "POST":
        cambios, errores = [], []
        try:
            for prefix, item_type, items in (("p_", "product", productos), ("m_", "material", materiales)):
                for it in items:
                    raw = request.form.get(f"{prefix}{it.id}", "")
                    try:
                        real = _num(raw)
                    except ValueError:
                        errores.append(f"{it.nombre}: '{raw}' no es un número válido (no se cambió).")
                        continue
                    if real is None:
                        continue
                    diff = set_stock_to(item_type, it.id, real, commit=False)
                    if diff:
                        cambios.append(f"{it.nombre}: ajuste de {diff:+g}")
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        flash(f"Conteo guardado: {len(cambios)} ítems ajustados.", "success")
        for c in cambios[:40]:
            flash(c, "success")
        for e in errores:
            flash(e, "warning")
        return redirect(url_for("stocktake.conteo"))

    filas_p = [(p, calculate_product_stock(p.id)) for p in productos]
    filas_m = [(m, calculate_raw_material_stock(m.id)) for m in materiales]
    return render_template("stocktake.html", filas_p=filas_p, filas_m=filas_m)
