"""
Importación de datos históricos vía CSV (sección 29 del documento).

Formatos esperados:

ventas.csv:   fecha,producto,cantidad,precio,cliente_o_canal
compras.csv:  fecha,materia_prima,cantidad,costo,proveedor

Donde 'producto' / 'materia_prima' se buscan por nombre (deben existir
previamente). 'cliente_o_canal': si coincide con el nombre de un cliente
existente se asocia como venta B2B; si no, se usa como canal de venta.
"""
import csv
import io
from datetime import datetime

from models.products import Product
from models.raw_materials import RawMaterial
from models.customers import Customer
from services.sales_engine import register_sale
from services.purchasing_engine import register_purchase


def _parse_date(value):
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha no reconocida: {value}")


def import_sales_csv(file_stream):
    reader = csv.DictReader(io.TextIOWrapper(file_stream, encoding="utf-8"))
    productos = {p.nombre.strip().lower(): p for p in Product.query.all()}
    clientes = {c.nombre.strip().lower(): c for c in Customer.query.all()}

    creadas, errores = 0, []
    for i, row in enumerate(reader, start=2):
        try:
            producto = productos.get(row["producto"].strip().lower())
            if not producto:
                raise ValueError(f"Producto '{row['producto']}' no existe")
            cliente_o_canal = (row.get("cliente_o_canal") or "").strip()
            cliente = clientes.get(cliente_o_canal.lower())
            register_sale(
                product_id=producto.id,
                cantidad=float(row["cantidad"]),
                precio=float(row["precio"]),
                canal=cliente_o_canal if not cliente else (cliente.tipo or "Otro B2B"),
                customer_id=cliente.id if cliente else None,
                fecha=_parse_date(row["fecha"]),
            )
            creadas += 1
        except Exception as e:  # noqa: BLE001 — reportamos fila por fila
            errores.append(f"Fila {i}: {e}")

    return {"creadas": creadas, "errores": errores}


def import_purchases_csv(file_stream):
    reader = csv.DictReader(io.TextIOWrapper(file_stream, encoding="utf-8"))
    materiales = {m.nombre.strip().lower(): m for m in RawMaterial.query.all()}

    creadas, errores = 0, []
    for i, row in enumerate(reader, start=2):
        try:
            material = materiales.get(row["materia_prima"].strip().lower())
            if not material:
                raise ValueError(f"Materia prima '{row['materia_prima']}' no existe")
            register_purchase(
                raw_material_id=material.id,
                cantidad=float(row["cantidad"]),
                costo_total=float(row["costo"]) if row.get("costo") else None,
                proveedor=row.get("proveedor"),
                fecha=_parse_date(row["fecha"]),
            )
            creadas += 1
        except Exception as e:  # noqa: BLE001
            errores.append(f"Fila {i}: {e}")

    return {"creadas": creadas, "errores": errores}
