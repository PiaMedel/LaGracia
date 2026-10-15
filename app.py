import os
import time
from flask import Flask, abort, request
from config import Config
from extensions import db

# Hora de Chile para todo lo que dependa de "hoy" (el servidor corre en UTC).
os.environ.setdefault("TZ", "America/Santiago")
try:
    time.tzset()
except AttributeError:  # Windows
    pass

BLOQUEADAS_MODO_SIMPLE = (
    "/produccion", "/compras", "/clientes", "/pedidos",
    "/preparaciones", "/indicadores", "/portafolio", "/api/b2b",
)
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def ensure_schema():
    """db.create_all() crea tablas nuevas pero NO agrega columnas a tablas que ya
    existen. Esta función agrega, de forma segura y repetible, las columnas que
    se incorporaron después de la primera versión (conserva todos los datos)."""
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    if "waste" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("waste")}
    with db.engine.begin() as conn:
        if "tipo" not in cols:
            conn.execute(text("ALTER TABLE waste ADD COLUMN tipo VARCHAR(20) DEFAULT 'Merma'"))
        if "nota" not in cols:
            conn.execute(text("ALTER TABLE waste ADD COLUMN nota VARCHAR(255)"))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)
    db.init_app(app)

    # importar modelos para que SQLAlchemy los registre antes de create_all
    import models  # noqa: F401

    with app.app_context():
        db.create_all()
        ensure_schema()

    # ---- blueprints ----
    from routes.dashboard import bp as dashboard_bp
    from routes.products import bp as products_bp
    from routes.inventory import bp as inventory_bp
    from routes.production import bp as production_bp
    from routes.purchases import bp as purchases_bp
    from routes.sales import bp as sales_bp
    from routes.customers import bp as customers_bp
    from routes.orders import bp as orders_bp
    from routes.waste import bp as waste_bp
    from routes.imports import bp as imports_bp
    from routes.preparations import bp as preparations_bp
    from routes.stocktake import bp as stocktake_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(purchases_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(waste_bp)
    app.register_blueprint(imports_bp)
    app.register_blueprint(stocktake_bp)
    if app.config.get("USAR_PRE_PREPARACIONES"):
        app.register_blueprint(preparations_bp)

    @app.before_request
    def _bloquear_modulos_desactivados():
        if app.config.get("MODO_SIMPLE") and request.path.startswith(BLOQUEADAS_MODO_SIMPLE):
            abort(404)

    @app.context_processor
    def inject_globals():
        from datetime import date
        hoy = date.today()
        return {
            "hoy_fecha": hoy,
            "fecha_larga": f"{_DIAS[hoy.weekday()].capitalize()} {hoy.day} de {_MESES[hoy.month - 1]} de {hoy.year}",
            "usar_preps": app.config.get("USAR_PRE_PREPARACIONES", False),
            "modo_simple": app.config.get("MODO_SIMPLE", False),
        }

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
