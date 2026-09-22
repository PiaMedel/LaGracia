from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from models.products import Product, ESTADOS_PRODUCTO
from models.raw_materials import RawMaterial
from models.preparations import Preparation
from models.recipes import Recipe, RecipeItem
from services.costing_engine import calculate_margin
from services.inventory_engine import calculate_product_stock, registrar_movimiento

bp = Blueprint("products", __name__, url_prefix="/productos")


@bp.route("/")
def listar():
    productos = Product.query.order_by(Product.nombre).all()
    filas = []
    for p in productos:
        margen = calculate_margin(p)
        filas.append({
            "product": p,
            "stock": calculate_product_stock(p.id),
            "margen": margen,
        })
    return render_template("products/list.html", filas=filas)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        p = Product(
            nombre=request.form["nombre"],
            categoria=request.form.get("categoria"),
            unidad_venta=request.form.get("unidad_venta", "unidad"),
            precio_venta=float(request.form.get("precio_venta") or 0),
            estado=request.form.get("estado", "POTENCIAL"),
            stock_seguridad=float(request.form.get("stock_seguridad") or 0),
            vida_util_dias=int(request.form["vida_util_dias"]) if request.form.get("vida_util_dias") else None,
        )
        db.session.add(p)
        db.session.flush()
        stock_inicial = float(request.form.get("stock_inicial") or 0)
        if stock_inicial:
            registrar_movimiento("product", p.id, stock_inicial, "stock_inicial", commit=False)
        db.session.commit()
        flash(f"Producto '{p.nombre}' creado.", "success")
        return redirect(url_for("products.listar"))
    return render_template("products/form.html", producto=None, estados=ESTADOS_PRODUCTO)


@bp.route("/<int:product_id>/editar", methods=["GET", "POST"])
def editar(product_id):
    p = Product.query.get_or_404(product_id)
    if request.method == "POST":
        p.nombre = request.form["nombre"]
        p.categoria = request.form.get("categoria")
        p.unidad_venta = request.form.get("unidad_venta", "unidad")
        p.precio_venta = float(request.form.get("precio_venta") or 0)
        p.estado = request.form.get("estado", p.estado)
        p.stock_seguridad = float(request.form.get("stock_seguridad") or 0)
        p.vida_util_dias = int(request.form["vida_util_dias"]) if request.form.get("vida_util_dias") else None
        p.activo = bool(request.form.get("activo"))
        db.session.commit()
        flash(f"Producto '{p.nombre}' actualizado.", "success")
        return redirect(url_for("products.listar"))
    return render_template("products/form.html", producto=p, estados=ESTADOS_PRODUCTO)


@bp.route("/<int:product_id>/receta", methods=["GET", "POST"])
def receta(product_id):
    p = Product.query.get_or_404(product_id)
    recipe = p.recipe

    if request.method == "POST":
        rendimiento = float(request.form["rendimiento"])
        if recipe is None:
            recipe = Recipe(product_id=p.id, rendimiento=rendimiento)
            db.session.add(recipe)
        else:
            recipe.rendimiento = rendimiento
            RecipeItem.query.filter_by(recipe_id=recipe.id).delete()
        db.session.flush()

        ingredient_types = request.form.getlist("ingredient_type")
        ingredient_ids = request.form.getlist("ingredient_id")
        cantidades = request.form.getlist("cantidad")
        for itype, ingid, cant in zip(ingredient_types, ingredient_ids, cantidades):
            if ingid and cant:
                if itype == "preparation":
                    db.session.add(RecipeItem(
                        recipe_id=recipe.id, ingredient_type="preparation",
                        preparation_id=int(ingid), cantidad=float(cant),
                    ))
                else:
                    db.session.add(RecipeItem(
                        recipe_id=recipe.id, ingredient_type="material",
                        raw_material_id=int(ingid), cantidad=float(cant),
                    ))
        db.session.commit()
        flash("Receta guardada.", "success")
        return redirect(url_for("products.listar"))

    materiales = RawMaterial.query.filter_by(activo=True).order_by(RawMaterial.nombre).all()
    preparaciones = Preparation.query.filter_by(activo=True).order_by(Preparation.nombre).all()
    margen = calculate_margin(p)
    return render_template(
        "products/recipe_form.html", producto=p, recipe=recipe,
        materiales=materiales, preparaciones=preparaciones, margen=margen,
    )
