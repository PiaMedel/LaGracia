import os
from flask import Flask
from config import Config
from extensions import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)
    db.init_app(app)

    # importar modelos para que SQLAlchemy los registre antes de create_all
    import models  # noqa: F401

    with app.app_context():
        db.create_all()

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
    app.register_blueprint(preparations_bp)

    @app.context_processor
    def inject_globals():
        from datetime import date
        return {"hoy_fecha": date.today()}

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
