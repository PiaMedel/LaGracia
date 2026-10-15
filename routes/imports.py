from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, current_app
from services.import_engine import import_sales_csv, import_purchases_csv
from services.bulk_import_engine import import_catalog, build_template_bytes
from services.movements_import_engine import import_movements, build_movements_template
from extensions import db

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


@bp.route("/plantilla-catalogo")
def plantilla_catalogo():
    return send_file(
        build_template_bytes(current_app.config.get("USAR_PRE_PREPARACIONES", False)),
        as_attachment=True,
        download_name="plantilla_catalogo_la_gracia.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/catalogo", methods=["POST"])
def importar_catalogo():
    archivo = request.files.get("archivo")
    if not archivo or archivo.filename == "":
        flash("Selecciona el archivo Excel (.xlsx).", "danger")
        return redirect(url_for("imports.importar"))
    if not archivo.filename.lower().endswith(".xlsx"):
        flash("El archivo debe ser un Excel (.xlsx). Si lo tienes en CSV, ábrelo y guárdalo como Excel.", "danger")
        return redirect(url_for("imports.importar"))

    try:
        resultados = import_catalog(archivo.stream)
    except Exception as e:  # noqa: BLE001
        flash(f"No se pudo leer el archivo: {e}", "danger")
        return redirect(url_for("imports.importar"))

    todos_errores = []
    for hoja, r in resultados.items():
        if r["creados"] or r["actualizados"]:
            flash(f"{hoja}: {r['creados']} nuevos, {r['actualizados']} actualizados.", "success")
        todos_errores.extend(r["errores"])
    if not any(r["creados"] or r["actualizados"] for r in resultados.values()) and not todos_errores:
        flash("El archivo no tenía filas para importar (¿solo la fila de ejemplo?).", "warning")
    for err in todos_errores[:30]:
        flash(err, "warning")
    if len(todos_errores) > 30:
        flash(f"... y {len(todos_errores) - 30} avisos más.", "warning")
    return redirect(url_for("imports.importar"))


@bp.route("/plantilla-movimientos")
def plantilla_movimientos():
    from datetime import date
    return send_file(
        build_movements_template(),
        as_attachment=True,
        download_name=f"excel_base_movimientos_{date.today():%Y-%m-%d}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/movimientos", methods=["POST"])
def importar_movimientos():
    archivo = request.files.get("archivo")
    if not archivo or archivo.filename == "":
        flash("Selecciona el archivo Excel (.xlsx).", "danger")
        return redirect(url_for("imports.importar"))
    if not archivo.filename.lower().endswith(".xlsx"):
        flash("El archivo debe ser un Excel (.xlsx).", "danger")
        return redirect(url_for("imports.importar"))

    res = import_movements(archivo.read(), archivo.filename,
                           allow_duplicate=bool(request.form.get("permitir_repetido")))
    if res["ok"]:
        r = res["resumen"]
        flash(f"Carga exitosa: {r['producciones']} ingresos de productos (materias primas descontadas), "
              f"{r['compras']} compras, {r['ventas']} ventas, {r['salidas']} mermas/regalos/muestras.", "success")
    else:
        flash("NO se cargó nada. Corrige lo siguiente y vuelve a subir el archivo:", "danger")
    for e in res["errores"][:40]:
        flash(e, "warning")
    if len(res["errores"]) > 40:
        flash(f"... y {len(res['errores']) - 40} errores más.", "warning")
    for a in res["avisos"]:
        flash(a, "warning")
    return redirect(url_for("imports.importar"))


@bp.route("/borrar", methods=["POST"])
def borrar():
    """Zona de peligro. Requiere escribir BORRAR."""
    if (request.form.get("confirmacion") or "").strip().upper() != "BORRAR":
        flash("No se borró nada: debes escribir la palabra BORRAR para confirmar.", "danger")
        return redirect(url_for("imports.importar"))

    alcance = request.form.get("alcance")
    db.session.rollback()
    if alcance == "todo":
        db.session.close()
        db.drop_all()
        db.create_all()
        flash("Se borró TODO (productos, materias primas, recetas y movimientos). La app quedó vacía.", "success")
    elif alcance == "movimientos":
        from models import (StockMovement, Sale, Purchase, Production, PreparationProduction,
                            Waste, OrderItem, Order, ImportLog)
        for model in (StockMovement, Sale, Purchase, Production, PreparationProduction,
                      Waste, OrderItem, Order, ImportLog):
            db.session.query(model).delete()
        db.session.commit()
        flash("Se borraron todos los movimientos (producción, compras, ventas, conteos y ajustes). "
              "Se conservaron productos, materias primas y recetas.", "success")
    else:
        flash("Opción no válida.", "danger")
    return redirect(url_for("imports.importar"))
