"""
Motor de automatización B2B (secciones 13, 14 del documento).

Responde: ¿a quién debemos contactar hoy?
"""
from datetime import date, timedelta
from models.customers import Customer


def _mensaje_prearmado(customer):
    return (
        f"Hola {customer.nombre} 😊, ¿cómo están? Estamos preparando la producción "
        f"de esta semana y quería saber si necesitan reposición de "
        f"{customer.producto_habitual.nombre if customer.producto_habitual else 'productos'}."
    )


def calculate_b2b_followups(dias_anticipacion=0):
    """Devuelve la lista de clientes a contactar hoy (o antes de N días),
    junto con la urgencia del contacto.

    Regla: si proximo_seguimiento fue pospuesto manualmente, se respeta esa
    fecha por sobre el cálculo automático de frecuencia.
    """
    today = date.today()
    limite = today + timedelta(days=dias_anticipacion)
    resultados = []

    clientes = Customer.query.filter(Customer.estado == "Activo").all()
    for c in clientes:
        fecha_objetivo = None
        origen = None

        if c.proximo_seguimiento:
            fecha_objetivo = c.proximo_seguimiento
            origen = "pospuesto_manual"
        elif c.ultimo_pedido and c.frecuencia_habitual_dias:
            fecha_objetivo = c.ultimo_pedido + timedelta(days=c.frecuencia_habitual_dias)
            origen = "frecuencia_historica"

        if fecha_objetivo is None:
            continue

        if fecha_objetivo <= limite:
            dias_atraso = (today - fecha_objetivo).days
            if dias_atraso > 0:
                urgencia = "atrasado"
            elif fecha_objetivo == today:
                urgencia = "hoy"
            else:
                urgencia = "proximo"

            resultados.append({
                "customer_id": c.id,
                "cliente": c.nombre,
                "tipo": c.tipo,
                "whatsapp": c.whatsapp,
                "fecha_objetivo": fecha_objetivo.isoformat(),
                "dias_atraso": max(dias_atraso, 0),
                "urgencia": urgencia,
                "origen": origen,
                "cantidad_promedio": c.cantidad_promedio,
                "producto_habitual": c.producto_habitual.nombre if c.producto_habitual else None,
                "mensaje_whatsapp": _mensaje_prearmado(c),
            })

    orden_urgencia = {"atrasado": 0, "hoy": 1, "proximo": 2}
    resultados.sort(key=lambda r: (orden_urgencia.get(r["urgencia"], 9), -r["dias_atraso"]))
    return resultados


def postpone_followup(customer_id, dias):
    from extensions import db
    c = Customer.query.get(customer_id)
    if c is None:
        raise ValueError("Cliente no encontrado")
    base = c.proximo_seguimiento or date.today()
    c.proximo_seguimiento = base + timedelta(days=dias)
    db.session.commit()
    return c


def register_contact(customer_id, fecha=None):
    from extensions import db
    c = Customer.query.get(customer_id)
    if c is None:
        raise ValueError("Cliente no encontrado")
    c.ultimo_contacto = fecha or date.today()
    db.session.commit()
    return c
