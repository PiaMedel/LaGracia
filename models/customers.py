from extensions import db

TIPOS_CLIENTE = ["Cafetería", "Hotel", "Tienda", "Restaurant", "Otro"]


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    tipo = db.Column(db.String(30), default="Otro")
    contacto = db.Column(db.String(120))
    whatsapp = db.Column(db.String(30))
    estado = db.Column(db.String(20), default="Activo")  # Activo / Inactivo
    frecuencia_habitual_dias = db.Column(db.Integer)  # ej. 7 = compra cada 7 días
    dia_habitual = db.Column(db.String(20))  # ej. "Jueves"
    ultimo_pedido = db.Column(db.Date)
    ultimo_contacto = db.Column(db.Date)
    proximo_seguimiento = db.Column(db.Date)  # se puede posponer manualmente
    cantidad_promedio = db.Column(db.Float)
    precio_acordado = db.Column(db.Float)
    producto_habitual_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)

    producto_habitual = db.relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "tipo": self.tipo,
            "contacto": self.contacto,
            "whatsapp": self.whatsapp,
            "estado": self.estado,
            "frecuencia_habitual_dias": self.frecuencia_habitual_dias,
            "dia_habitual": self.dia_habitual,
            "ultimo_pedido": self.ultimo_pedido.isoformat() if self.ultimo_pedido else None,
            "ultimo_contacto": self.ultimo_contacto.isoformat() if self.ultimo_contacto else None,
            "proximo_seguimiento": self.proximo_seguimiento.isoformat() if self.proximo_seguimiento else None,
            "cantidad_promedio": self.cantidad_promedio,
            "precio_acordado": self.precio_acordado,
            "producto_habitual_id": self.producto_habitual_id,
        }
