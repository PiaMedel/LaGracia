from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from models.raw_materials import RawMaterial
from services.inventory_engine import calculate_raw_material_stock, registrar_movimiento, movement_history
from services.purchasing_engine import suggest_purchase, reposicion_point
from services.expiry_engine import check_item_expiry

bp = Blueprint("inventory", __name__, url_prefix="/materias-primas")


@bp.route("/")
def listar():
    materiales = RawMaterial.query.order_by(RawMaterial.nombre).all()
    filas = []
    for m in materiales:
        filas.append({
            "material": m,
            "stock": calculate_raw_material_stock(m.id),
            "punto_reposicion": reposicion_point(m),
            "alerta": check_item_expiry("material", m.id, m.vida_util_dias),
        })
    return render_template("inventory/list.html", filas=filas)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        m = RawMaterial(
            nombre=request.form["nombre"],
            unidad_medida=request.form.get("unidad_medida", "kg"),
            stock_seguridad=float(request.form.get("stock_seguridad") or 0),
            consumo_diario_estimado=float(request.form.get("consumo_diario_estimado") or 0),
            dias_reposicion=int(request.form.get("dias_reposicion") or 0),
            compra_minima=float(request.form.get("compra_minima") or 0),
            costo_unitario=float(request.form.get("costo_unitario") or 0),
            vida_util_dias=int(request.form["vida_util_dias"]) if request.form.get("vida_util_dias") else None,
            proveedor=request.form.get("proveedor"),
        )
        db.session.add(m)
        db.session.flush()
        stock_inicial = float(request.form.get("stock_inicial") or 0)
        if stock_inicial:
            registrar_movimiento("material", m.id, stock_inicial, "stock_inicial", commit=False)
        db.session.commit()
        flash(f"Materia prima '{m.nombre}' creada.", "success")
        return redirect(url_for("inventory.listar"))
    return render_template("inventory/form.html", material=None)


@bp.route("/<int:material_id>/editar", methods=["GET", "POST"])
def editar(material_id):
    m = RawMaterial.query.get_or_404(material_id)
    if request.method == "POST":
        m.nombre = request.form["nombre"]
        m.unidad_medida = request.form.get("unidad_medida", "kg")
        m.stock_seguridad = float(request.form.get("stock_seguridad") or 0)
        m.consumo_diario_estimado = float(request.form.get("consumo_diario_estimado") or 0)
        m.dias_reposicion = int(request.form.get("dias_reposicion") or 0)
        m.compra_minima = float(request.form.get("compra_minima") or 0)
        m.costo_unitario = float(request.form.get("costo_unitario") or 0)
        m.vida_util_dias = int(request.form["vida_util_dias"]) if request.form.get("vida_util_dias") else None
        m.proveedor = request.form.get("proveedor")
        m.activo = bool(request.form.get("activo"))
        db.session.commit()
        flash(f"Materia prima '{m.nombre}' actualizada.", "success")
        return redirect(url_for("inventory.listar"))
    return render_template("inventory/form.html", material=m)


@bp.route("/<int:material_id>/movimientos")
def movimientos(material_id):
    m = RawMaterial.query.get_or_404(material_id)
    historial = movement_history("material", material_id)
    detalle_compra = suggest_purchase(material_id)
    return render_template("inventory/movements.html", material=m, historial=historial, detalle=detalle_compra)


@bp.route("/<int:material_id>/ajuste", methods=["POST"])
def ajuste(material_id):
    cantidad = float(request.form["cantidad"])
    nota = request.form.get("nota", "Ajuste manual")
    registrar_movimiento("material", material_id, cantidad, "ajuste", referencia_tipo="manual", nota=nota)
    flash("Ajuste registrado.", "success")
    return redirect(url_for("inventory.movimientos", material_id=material_id))
