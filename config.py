import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _normalized_database_url():
    """Railway (y otros hosts) a veces entregan la URL de Postgres con el
    prefijo antiguo 'postgres://', que SQLAlchemy 1.4+ ya no acepta
    (requiere 'postgresql://'). Si no hay DATABASE_URL en el entorno,
    usamos SQLite local (para desarrollo en tu computador)."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return f"sqlite:///{os.path.join(BASE_DIR, 'database', 'la_gracia.db')}"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "la-gracia-dev-secret")
    SQLALCHEMY_DATABASE_URI = _normalized_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Módulo de pre-preparaciones (semi-elaborados congelados). APAGADO por defecto:
    # la app trabaja solo con materias primas -> productos. Para encenderlo,
    # definir la variable de entorno USAR_PRE_PREPARACIONES=1 (p. ej. en Railway).
    USAR_PRE_PREPARACIONES = os.environ.get("USAR_PRE_PREPARACIONES", "0") == "1"

    # ---- Parámetros del motor de reglas (ajustables sin tocar código) ----
    # Horizonte de días hacia adelante para calcular demanda / sugerir producción
    HORIZONTE_DEMANDA_DIAS = 3
    # Horizonte de días hacia adelante para planificar compras
    HORIZONTE_COMPRAS_DIAS = 7
    # Ventana de días hacia atrás para estimar consumo diario / venta promedio
    VENTANA_HISTORICA_DIAS = 30
    # Ventana para detectar "compra hormiga"
    VENTANA_COMPRA_HORMIGA_DIAS = 20
    COMPRA_HORMIGA_MIN_COMPRAS = 5
    # Umbral de merma % sobre lo producido para generar alerta
    UMBRAL_MERMA_ALERTA_PCT = 8.0
    # Si la producción sugerida incluye o no el stock de seguridad
    # (ver nota de inconsistencia en el documento original, sección 4 vs 15)
    INCLUIR_STOCK_SEGURIDAD_EN_SUGERENCIA = True
