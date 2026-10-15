from flask import Blueprint, render_template, jsonify, current_app
from services.dashboard_engine import build_hoy_dashboard, build_indicators_dashboard, build_simple_hoy
from services.b2b_engine import postpone_followup, register_contact
from services.portfolio_engine import classify_all_products

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def hoy():
    if current_app.config.get("MODO_SIMPLE"):
        return render_template("hoy_simple.html", data=build_simple_hoy())
    data = build_hoy_dashboard()
    return render_template("hoy.html", data=data)


@bp.route("/indicadores")
def indicadores():
    data = build_indicators_dashboard()
    return render_template("indicadores.html", data=data)


@bp.route("/portafolio")
def portafolio():
    clasificacion = classify_all_products()
    return render_template("portafolio.html", clasificacion=clasificacion)


# ---- acciones rápidas desde la pantalla HOY (B2B) ----
@bp.route("/api/b2b/<int:customer_id>/contactar", methods=["POST"])
def api_contactar(customer_id):
    c = register_contact(customer_id)
    return jsonify({"ok": True, "cliente": c.nombre})


@bp.route("/api/b2b/<int:customer_id>/posponer/<int:dias>", methods=["POST"])
def api_posponer(customer_id, dias):
    c = postpone_followup(customer_id, dias)
    return jsonify({"ok": True, "cliente": c.nombre, "proximo_seguimiento": c.proximo_seguimiento.isoformat()})


# ---- API JSON (para integraciones futuras: apps móviles, TUU, WhatsApp, IA) ----
@bp.route("/api/hoy")
def api_hoy():
    return jsonify(build_hoy_dashboard())
