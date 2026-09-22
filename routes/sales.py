from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.products import Product
from models.customers import Customer
from models.sales import Sale, CANALES_VENTA
from services.sales_engine import register_sale

bp = Blueprint("sales", __name__, url_prefix="/ventas")


@bp.route("/")
def listar():
    ventas = Sale.query.order_by(Sale.fecha.desc()).limit(100).all()
    return render_template("sales/list.html", ventas=ventas)


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    if request.method == "POST":
        register_sale(
            product_id=int(request.form["product_id"]),
            cantidad=float(request.form["cantidad"]),
            precio=float(request.form["precio"]),
            canal=request.form.get("canal", "Venta directa"),
            customer_id=int(request.form["customer_id"]) if request.form.get("customer_id") else None,
        )
        flash("Venta registrada. Stock actualizado automáticamente.", "success")
        return redirect(url_for("sales.listar"))
    productos = Product.query.filter_by(activo=True).order_by(Product.nombre).all()
    clientes = Customer.query.order_by(Customer.nombre).all()
    return render_template("sales/form.html", productos=productos, clientes=clientes, canales=CANALES_VENTA)
