from flask import Blueprint, render_template, request, flash, redirect, url_for
from services.import_engine import import_sales_csv, import_purchases_csv

bp = Blueprint("imports", __name__, url_prefix="/importar")


@bp.route("/", methods=["GET", "POST"])
def importar():
    if request.method == "POST":
        tipo = request.form.get("tipo")
        archivo = request.files.get("archivo")
        if not archivo or archivo.filename == "":
            flash("Selecciona un archivo CSV.", "danger")
            return redirect(url_for("imports.importar"))

        if tipo == "ventas":
            resultado = import_sales_csv(archivo.stream)
        elif tipo == "compras":
            resultado = import_purchases_csv(archivo.stream)
        else:
            flash("Tipo de importación no válido.", "danger")
            return redirect(url_for("imports.importar"))

        flash(f"{resultado['creadas']} filas importadas correctamente.", "success")
        if resultado["errores"]:
            for err in resultado["errores"][:15]:
                flash(err, "warning")
        return redirect(url_for("imports.importar"))

    return render_template("imports/form.html")
