from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from models.orders import Order, OrderItem, TIPOS_PEDIDO, ESTADOS_PEDIDO
from models.customers import Customer
from models.products import Product
from services.sales_engine import register_sale

bp = Blueprint("orders", __name__, url_prefix="/pedidos")


@bp.route("/")
def listar():
    pedidos = Order.query.order_by(Order.fecha_entrega).all()
    return render_template("orders/list.html", pedidos=pedidos)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        o = Order(
            tipo=request.form.get("tipo", "Pedido B2B"),
            customer_id=int(request.form["customer_id"]) if request.form.get("customer_id") else None,
            fecha_entrega=datetime.strptime(request.form["fecha_entrega"], "%Y-%m-%d").date(),
            estado=request.form.get("estado", "Pendiente"),
            notas=request.form.get("notas"),
        )
        db.session.add(o)
        db.session.flush()

        product_ids = request.form.getlist("product_id")
        cantidades = request.form.getlist("cantidad")
        precios = request.form.getlist("precio")
        for pid, cant, precio in zip(product_ids, cantidades, precios):
            if pid and cant:
                db.session.add(OrderItem(
                    order_id=o.id, product_id=int(pid), cantidad=float(cant),
                    precio=float(precio) if precio else None,
                ))
        db.session.commit()
        flash(f"Pedido #{o.id} creado ({o.estado}).", "success")
        return redirect(url_for("orders.listar"))

    clientes = Customer.query.order_by(Customer.nombre).all()
    productos = Product.query.filter_by(activo=True).order_by(Product.nombre).all()
    return render_template("orders/form.html", clientes=clientes, productos=productos, tipos=TIPOS_PEDIDO, estados=ESTADOS_PEDIDO)


@bp.route("/<int:order_id>/estado", methods=["POST"])
def cambiar_estado(order_id):
    o = Order.query.get_or_404(order_id)
    nuevo_estado = request.form["estado"]
    o.estado = nuevo_estado

    # Regla: al marcar un pedido como Entregado, se genera automáticamente
    # la venta correspondiente (para no duplicar el registro manual).
    if nuevo_estado == "Entregado":
        for item in o.items:
            register_sale(
                product_id=item.product_id,
                cantidad=item.cantidad,
                precio=item.precio or 0,
                canal=o.customer.tipo if o.customer else "Otro B2B",
                customer_id=o.customer_id,
                order_id=o.id,
            )
    db.session.commit()
    flash(f"Pedido #{o.id} marcado como {nuevo_estado}.", "success")
    return redirect(url_for("orders.listar"))
