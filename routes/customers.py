from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from models.customers import Customer, TIPOS_CLIENTE
from models.products import Product

bp = Blueprint("customers", __name__, url_prefix="/clientes")


@bp.route("/")
def listar():
    clientes = Customer.query.order_by(Customer.nombre).all()
    return render_template("customers/list.html", clientes=clientes)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        c = Customer(
            nombre=request.form["nombre"],
            tipo=request.form.get("tipo", "Otro"),
            contacto=request.form.get("contacto"),
            whatsapp=request.form.get("whatsapp"),
            estado=request.form.get("estado", "Activo"),
            frecuencia_habitual_dias=int(request.form["frecuencia_habitual_dias"]) if request.form.get("frecuencia_habitual_dias") else None,
            dia_habitual=request.form.get("dia_habitual"),
            cantidad_promedio=float(request.form["cantidad_promedio"]) if request.form.get("cantidad_promedio") else None,
            precio_acordado=float(request.form["precio_acordado"]) if request.form.get("precio_acordado") else None,
            producto_habitual_id=int(request.form["producto_habitual_id"]) if request.form.get("producto_habitual_id") else None,
            ultimo_pedido=datetime.strptime(request.form["ultimo_pedido"], "%Y-%m-%d").date() if request.form.get("ultimo_pedido") else None,
        )
        db.session.add(c)
        db.session.commit()
        flash(f"Cliente '{c.nombre}' creado.", "success")
        return redirect(url_for("customers.listar"))
    productos = Product.query.order_by(Product.nombre).all()
    return render_template("customers/form.html", cliente=None, tipos=TIPOS_CLIENTE, productos=productos)


@bp.route("/<int:customer_id>/editar", methods=["GET", "POST"])
def editar(customer_id):
    c = Customer.query.get_or_404(customer_id)
    if request.method == "POST":
        c.nombre = request.form["nombre"]
        c.tipo = request.form.get("tipo", "Otro")
        c.contacto = request.form.get("contacto")
        c.whatsapp = request.form.get("whatsapp")
        c.estado = request.form.get("estado", "Activo")
        c.frecuencia_habitual_dias = int(request.form["frecuencia_habitual_dias"]) if request.form.get("frecuencia_habitual_dias") else None
        c.dia_habitual = request.form.get("dia_habitual")
        c.cantidad_promedio = float(request.form["cantidad_promedio"]) if request.form.get("cantidad_promedio") else None
        c.precio_acordado = float(request.form["precio_acordado"]) if request.form.get("precio_acordado") else None
        c.producto_habitual_id = int(request.form["producto_habitual_id"]) if request.form.get("producto_habitual_id") else None
        if request.form.get("ultimo_pedido"):
            c.ultimo_pedido = datetime.strptime(request.form["ultimo_pedido"], "%Y-%m-%d").date()
        db.session.commit()
        flash(f"Cliente '{c.nombre}' actualizado.", "success")
        return redirect(url_for("customers.listar"))
    productos = Product.query.order_by(Product.nombre).all()
    return render_template("customers/form.html", cliente=c, tipos=TIPOS_CLIENTE, productos=productos)
