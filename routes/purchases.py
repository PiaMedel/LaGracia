from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.raw_materials import RawMaterial
from models.purchases import Purchase
from services.purchasing_engine import suggest_purchase_all, register_purchase, detect_compra_hormiga

bp = Blueprint("purchases", __name__, url_prefix="/compras")


@bp.route("/")
def listar():
    sugerencias = suggest_purchase_all()
    alertas_hormiga = detect_compra_hormiga()
    historial = Purchase.query.order_by(Purchase.fecha.desc()).limit(50).all()
    return render_template("purchases/list.html", sugerencias=sugerencias, alertas_hormiga=alertas_hormiga, historial=historial)


@bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        raw_material_id = int(request.form["raw_material_id"])
        cantidad = float(request.form["cantidad"])
        costo_total = float(request.form["costo_total"]) if request.form.get("costo_total") else None
        proveedor = request.form.get("proveedor")
        register_purchase(raw_material_id, cantidad, costo_total, proveedor)
        flash("Compra registrada. Stock actualizado automáticamente.", "success")
        return redirect(url_for("purchases.listar"))
    materiales = RawMaterial.query.filter_by(activo=True).order_by(RawMaterial.nombre).all()
    return render_template("purchases/register.html", materiales=materiales)
