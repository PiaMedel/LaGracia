from datetime import datetime
from extensions import db


class ImportLog(db.Model):
    """Registro de archivos de movimientos ya cargados (evita cargar dos veces
    el mismo Excel por error, lo que duplicaría stock y consumos)."""
    __tablename__ = "import_log"

    id = db.Column(db.Integer, primary_key=True)
    sha256 = db.Column(db.String(64), index=True, nullable=False)
    filename = db.Column(db.String(255))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    resumen = db.Column(db.String(500))
