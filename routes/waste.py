from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.products import Product
from models.raw_materials import RawMaterial
from models.waste import Waste, MOTIVOS_MERMA, TIPOS_SALIDA
from services.waste_engine import register_waste, waste_summary

bp = Blueprint("waste", __name__, url_prefix="/mermas")


@bp.route("/")
def listar():
    tipo = request.args.get("tipo")
    q = Waste.query
    if tipo in TIPOS_SALIDA:
        q = q.filter(Waste.tipo == tipo)
    registros = q.order_by(Waste.fecha.desc(), Waste.id.desc()).limit(200).all()
    return render_template("waste/list.html", registros=registros, tipo=tipo,
                           tipos=TIPOS_SALIDA, resumen=waste_summary(30))


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    if request.method == "POST":
        tipo = request.form.get("tipo", "Merma")
        item_type = request.form.get("item_type", "product")
        try:
            cantidad = float((request.form.get("cantidad") or "").replace(",", "."))
            if cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor que cero.")
            fecha = (datetime.strptime(request.form["fecha"], "%Y-%m-%d").date()
                     if request.form.get("fecha") else None)
            register_waste(
                item_type=item_type,
                cantidad=cantidad,
                motivo=request.form.get("motivo") if tipo == "Merma" else tipo,
                product_id=int(request.form["product_id"]) if item_type == "product" else None,
                raw_material_id=int(request.form["raw_material_id"]) if item_type == "material" else None,
                fecha=fecha,
                tipo=tipo,
                nota=request.form.get("nota"),
            )
        except (ValueError, KeyError) as e:
            flash(f"No se registró: {e}", "danger")
            return redirect(url_for("waste.nueva"))
        flash(f"{tipo} registrada. Stock actualizado automáticamente.", "success")
        return redirect(url_for("waste.listar"))
    productos = Product.query.filter_by(activo=True).order_by(Product.nombre).all()
    materiales = RawMaterial.query.filter_by(activo=True).order_by(RawMaterial.nombre).all()
    return render_template("waste/form.html", productos=productos, materiales=materiales,
                           motivos=MOTIVOS_MERMA, tipos=TIPOS_SALIDA)
