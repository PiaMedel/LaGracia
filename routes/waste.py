from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.products import Product
from models.raw_materials import RawMaterial
from models.waste import Waste, MOTIVOS_MERMA
from services.waste_engine import register_waste

bp = Blueprint("waste", __name__, url_prefix="/mermas")


@bp.route("/")
def listar():
    mermas = Waste.query.order_by(Waste.fecha.desc()).limit(100).all()
    return render_template("waste/list.html", mermas=mermas)


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    if request.method == "POST":
        item_type = request.form["item_type"]
        register_waste(
            item_type=item_type,
            cantidad=float(request.form["cantidad"]),
            motivo=request.form.get("motivo", "Otro"),
            product_id=int(request.form["product_id"]) if item_type == "product" else None,
            raw_material_id=int(request.form["raw_material_id"]) if item_type == "material" else None,
        )
        flash("Merma registrada. Stock actualizado automáticamente.", "success")
        return redirect(url_for("waste.listar"))
    productos = Product.query.filter_by(activo=True).order_by(Product.nombre).all()
    materiales = RawMaterial.query.filter_by(activo=True).order_by(RawMaterial.nombre).all()
    return render_template("waste/form.html", productos=productos, materiales=materiales, motivos=MOTIVOS_MERMA)
