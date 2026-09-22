from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from models.preparations import Preparation, PreparationRecipe, PreparationRecipeItem, PreparationProduction
from models.raw_materials import RawMaterial
from services.inventory_engine import calculate_preparation_stock, registrar_movimiento, movement_history
from services.costing_engine import calculate_preparation_cost, calculate_preparation_unit_cost
from services.preparation_engine import (
    suggest_preparation_production_all,
    execute_preparation_production,
    check_expiry_alert,
)

bp = Blueprint("preparations", __name__, url_prefix="/preparaciones")


@bp.route("/")
def listar():
    preparaciones = Preparation.query.order_by(Preparation.nombre).all()
    filas = []
    for p in preparaciones:
        filas.append({
            "prep": p,
            "stock": calculate_preparation_stock(p.id),
            "costo_unitario": calculate_preparation_unit_cost(p),
            "alerta": check_expiry_alert(p),
        })
    return render_template("preparations/list.html", filas=filas)


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    if request.method == "POST":
        p = Preparation(
            nombre=request.form["nombre"],
            unidad_medida=request.form.get("unidad_medida", "kg"),
            stock_seguridad=float(request.form.get("stock_seguridad") or 0),
            vida_util_congelada_dias=int(request.form["vida_util_congelada_dias"]) if request.form.get("vida_util_congelada_dias") else None,
            vida_util_descongelada_dias=int(request.form["vida_util_descongelada_dias"]) if request.form.get("vida_util_descongelada_dias") else None,
        )
        db.session.add(p)
        db.session.flush()
        stock_inicial = float(request.form.get("stock_inicial") or 0)
        if stock_inicial:
            registrar_movimiento("preparation", p.id, stock_inicial, "stock_inicial", commit=False)
        db.session.commit()
        flash(f"Preparación '{p.nombre}' creada.", "success")
        return redirect(url_for("preparations.listar"))
    return render_template("preparations/form.html", prep=None)


@bp.route("/<int:prep_id>/editar", methods=["GET", "POST"])
def editar(prep_id):
    p = Preparation.query.get_or_404(prep_id)
    if request.method == "POST":
        p.nombre = request.form["nombre"]
        p.unidad_medida = request.form.get("unidad_medida", "kg")
        p.stock_seguridad = float(request.form.get("stock_seguridad") or 0)
        p.vida_util_congelada_dias = int(request.form["vida_util_congelada_dias"]) if request.form.get("vida_util_congelada_dias") else None
        p.vida_util_descongelada_dias = int(request.form["vida_util_descongelada_dias"]) if request.form.get("vida_util_descongelada_dias") else None
        p.activo = bool(request.form.get("activo"))
        db.session.commit()
        flash(f"Preparación '{p.nombre}' actualizada.", "success")
        return redirect(url_for("preparations.listar"))
    return render_template("preparations/form.html", prep=p)


@bp.route("/<int:prep_id>/receta", methods=["GET", "POST"])
def receta(prep_id):
    p = Preparation.query.get_or_404(prep_id)
    recipe = p.recipe

    if request.method == "POST":
        rendimiento = float(request.form["rendimiento"])
        if recipe is None:
            recipe = PreparationRecipe(preparation_id=p.id, rendimiento=rendimiento)
            db.session.add(recipe)
        else:
            recipe.rendimiento = rendimiento
            PreparationRecipeItem.query.filter_by(recipe_id=recipe.id).delete()
        db.session.flush()

        material_ids = request.form.getlist("raw_material_id")
        cantidades = request.form.getlist("cantidad")
        for mid, cant in zip(material_ids, cantidades):
            if mid and cant:
                db.session.add(PreparationRecipeItem(recipe_id=recipe.id, raw_material_id=int(mid), cantidad=float(cant)))
        db.session.commit()
        flash("Receta de pre-preparación guardada.", "success")
        return redirect(url_for("preparations.listar"))

    materiales = RawMaterial.query.filter_by(activo=True).order_by(RawMaterial.nombre).all()
    costo_unitario = calculate_preparation_unit_cost(p)
    return render_template("preparations/recipe_form.html", prep=p, recipe=recipe, materiales=materiales, costo_unitario=costo_unitario)


@bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        preparation_id = int(request.form["preparation_id"])
        cantidad_real = float(request.form["cantidad_real"])
        execute_preparation_production(preparation_id, cantidad_real)
        flash("Pre-preparación registrada. Materias primas descontadas automáticamente.", "success")
        return redirect(url_for("preparations.listar"))
    preparaciones = [p for p in Preparation.query.filter_by(activo=True).all() if p.recipe]
    sugerencias = {s["preparation_id"]: s["produccion_sugerida"] for s in suggest_preparation_production_all()}
    return render_template("preparations/register.html", preparaciones=preparaciones, sugerencias=sugerencias)


@bp.route("/<int:prep_id>/movimientos")
def movimientos(prep_id):
    p = Preparation.query.get_or_404(prep_id)
    historial = movement_history("preparation", prep_id)
    return render_template("preparations/movements.html", prep=p, historial=historial)
