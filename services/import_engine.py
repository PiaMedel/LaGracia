"""
Importación de ventas y compras históricas desde CSV (sección 29 del documento).

Formatos esperados (nombres de columnas):
  ventas.csv:   fecha,producto,cantidad,precio,cliente_o_canal
  compras.csv:  fecha,materia_prima,cantidad,costo,proveedor

Tolera lo que exportan Excel / Numbers (también en Mac con configuración
regional en español):
  - separador de columnas ',' ';' o tabulación (se detecta solo)
  - UTF-8 con o sin BOM, o Latin-1
  - decimales con coma (0,5) y miles con punto en montos (60.000)
  - fechas 2026-08-01, 01/08/2026, 01-08-2026, 01/08/26
  - filas de ejemplo "(ejemplo) ..." y filas vacías se ignoran

Se hace UN solo commit al final y cada fila va en su propio savepoint:
una fila mala no afecta a las demás, y no hay riesgo de quedar a medias
por tiempo de espera cuando el archivo es grande.
"""
import csv
import io
import re
from datetime import datetime

from extensions import db
from models.products import Product
from models.raw_materials import RawMaterial
from models.customers import Customer
from services.sales_engine import register_sale
from services.purchasing_engine import register_purchase

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y")


def _parse_date(value):
    value = (value or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"fecha no reconocida: '{value}' (usa por ejemplo 2026-08-01 o 01/08/2026)")


def _to_float(value, money=False):
    s = str(value if value is not None else "").strip().replace("$", "").replace(" ", "")
    if s == "":
        raise ValueError("falta un número")
    if "," in s and "." in s:               # 1.234,50
        s = s.replace(".", "").replace(",", ".")
    elif money and re.fullmatch(r"\d{1,3}(\.\d{3})+", s):   # 60.000 (miles)
        s = s.replace(".", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        raise ValueError(f"número no válido: '{value}'")


def _read_rows(file_stream):
    """Devuelve lista de (n_fila, dict) con cabeceras normalizadas."""
    raw = file_stream.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    lines = text.splitlines()
    if not lines:
        return []
    head = lines[0]
    delim = max((";", ",", "\t"), key=head.count)
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    try:
        header = [(h or "").strip().lower().replace(" ", "_") for h in next(reader)]
    except StopIteration:
        return []
    rows = []
    for n, row in enumerate(reader, start=2):
        if not row or all((c or "").strip() == "" for c in row):
            continue
        d = {header[i]: (row[i].strip() if i < len(row) else "") for i in range(len(header))}
        first = next(iter(d.values()), "") if d else ""
        if any(v.lower().startswith("(ejemplo)") for v in list(d.values())[:3]):
            continue
        rows.append((n, d))
    return rows


def _require(row, cols):
    faltan = [c for c in cols if c not in row]
    if faltan:
        raise ValueError(
            f"el archivo no tiene la(s) columna(s): {', '.join(faltan)}. "
            f"Columnas encontradas: {', '.join(row.keys())}"
        )


def import_sales_csv(file_stream):
    rows = _read_rows(file_stream)
    productos = {p.nombre.strip().lower(): p for p in Product.query.all()}
    clientes = {c.nombre.strip().lower(): c for c in Customer.query.all()}

    creadas, errores = 0, []
    for n, row in rows:
        try:
            _require(row, ["fecha", "producto", "cantidad", "precio"])
            producto = productos.get(row["producto"].strip().lower())
            if not producto:
                raise ValueError(f"el producto '{row['producto']}' no existe (créalo primero)")
            cliente_o_canal = (row.get("cliente_o_canal") or "").strip()
            cliente = clientes.get(cliente_o_canal.lower()) if cliente_o_canal else None
            with db.session.begin_nested():
                register_sale(
                    product_id=producto.id,
                    cantidad=_to_float(row["cantidad"]),
                    precio=_to_float(row["precio"], money=True),
                    canal=(cliente.tipo or "Otro B2B") if cliente else (cliente_o_canal or "Venta directa"),
                    customer_id=cliente.id if cliente else None,
                    fecha=_parse_date(row["fecha"]),
                    commit=False,
                )
            creadas += 1
        except Exception as e:  # noqa: BLE001 — reportamos fila por fila
            errores.append(f"Fila {n}: {e}")
            if "no tiene la(s) columna(s)" in str(e):
                break  # error de estructura: no tiene sentido repetirlo por cada fila
    db.session.commit()
    return {"creadas": creadas, "errores": errores}


def import_purchases_csv(file_stream):
    rows = _read_rows(file_stream)
    materiales = {m.nombre.strip().lower(): m for m in RawMaterial.query.all()}

    creadas, errores = 0, []
    for n, row in rows:
        try:
            _require(row, ["fecha", "materia_prima", "cantidad"])
            material = materiales.get(row["materia_prima"].strip().lower())
            if not material:
                raise ValueError(f"la materia prima '{row['materia_prima']}' no existe (créala primero)")
            costo = row.get("costo", "")
            with db.session.begin_nested():
                register_purchase(
                    raw_material_id=material.id,
                    cantidad=_to_float(row["cantidad"]),
                    costo_total=_to_float(costo, money=True) if costo.strip() else None,
                    proveedor=row.get("proveedor") or None,
                    fecha=_parse_date(row["fecha"]),
                    commit=False,
                )
            creadas += 1
        except Exception as e:  # noqa: BLE001
            errores.append(f"Fila {n}: {e}")
            if "no tiene la(s) columna(s)" in str(e):
                break
    db.session.commit()
    return {"creadas": creadas, "errores": errores}
