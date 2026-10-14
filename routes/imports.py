from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, current_app
from services.import_engine import import_sales_csv, import_purchases_csv
from services.bulk_import_engine import import_catalog, build_template_bytes

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
