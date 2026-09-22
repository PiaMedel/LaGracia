from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.products import Product
from models.production import Production
from services.production_engine import suggest_production_all, plan_production, execute_production

bp = Blueprint("production", __name__, url_prefix="/produccion")


@bp.route("/")
def listar():
    sugerencias = suggest_production_all()
    historial = Production.query.order_by(Production.fecha.desc()).limit(50).all()
    return render_template("production/list.html", sugerencias=sugerencias, historial=historial)


@bp.route("/planificar", methods=["POST"])
def planificar():
    product_id = int(request.form["product_id"])
    cantidad_planificada = float(request.form["cantidad_planificada"])
    cantidad_sugerida = float(request.form.get("cantidad_sugerida") or 0)
    motivo = request.form.get("motivo_modificacion") or None
    if cantidad_sugerida and cantidad_planificada != cantidad_sugerida and not motivo:
        motivo = "Modificado sin motivo especificado"
    plan_production(product_id, cantidad_planificada, cantidad_sugerida, motivo)
    flash("Producción planificada.", "success")
    return redirect(url_for("production.listar"))


@bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        product_id = int(request.form["product_id"])
        cantidad_real = float(request.form["cantidad_real"])
        execute_production(product_id=product_id, cantidad_real=cantidad_real)
        flash("Producción registrada. Stock e insumos actualizados automáticamente.", "success")
        return redirect(url_for("production.listar"))
    productos = Product.query.filter_by(activo=True).order_by(Product.nombre).all()
    return render_template("production/register.html", productos=productos)


@bp.route("/<int:production_id>/ejecutar", methods=["POST"])
def ejecutar(production_id):
    cantidad_real = request.form.get("cantidad_real")
    execute_production(production_id=production_id, cantidad_real=float(cantidad_real) if cantidad_real else None)
    flash("Producción ejecutada. Stock e insumos actualizados automáticamente.", "success")
    return redirect(url_for("production.listar"))
