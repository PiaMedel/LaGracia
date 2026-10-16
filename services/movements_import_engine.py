"""
Excel base de MOVIMIENTOS (diario o semanal). Un solo archivo, tres hojas:

  1. Ingreso de productos    fecha | producto | cantidad
       -> suma stock del producto y DESCUENTA las materias primas según su receta
  2. Compras materias primas fecha | materia_prima | cantidad | costo_total | proveedor
       -> suma stock de la materia prima
  3. Ventas                  fecha | producto | cantidad | precio
       -> resta stock del producto
  4. Mermas y regalos        fecha | tipo | producto_o_materia_prima | cantidad | motivo | nota
       -> tipo = Merma, Regalo o Muestra; resta stock (regalos/muestras solo de productos)

La plantilla se genera con los productos y materias primas que YA existen en
la app, para que solo haya que escribir cantidades. Las filas sin cantidad se
ignoran.

Reglas de seguridad:
  - TODO O NADA: si una sola fila tiene error no se carga nada (así se puede
    corregir y volver a subir sin duplicar lo que sí estaba bien).
  - Los mismos movimientos (mismas fechas, productos y cantidades) no se pueden
    cargar dos veces, salvo que se marque expresamente.
"""
import hashlib
import io
from datetime import date, datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from extensions import db
from models.import_log import ImportLog
from models.products import Product
from models.waste import MOTIVOS_MERMA, TIPOS_SALIDA
from models.raw_materials import RawMaterial
from services.import_engine import _to_float
from services.inventory_engine import get_all_material_stocks, get_all_product_stocks
from services.production_engine import execute_production
from services.purchasing_engine import register_purchase
from services.sales_engine import register_sale
from services.waste_engine import register_waste

SHEET_PROD = "Ingreso de productos"
SHEET_BUY = "Compras materias primas"
SHEET_SALES = "Ventas"
SHEET_WASTE = "Mermas y regalos"

_FONT = "Arial"
_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y")

LEEME = [
    "CÓMO USAR ESTE EXCEL BASE (diario o semanal)",
    "",
    "1. Descarga este archivo desde la app cada vez (Importar → 'Descargar Excel base'): viene con tus productos y materias primas actuales.",
    "2. Escribe SOLO cantidades en las hojas que corresponda. Las filas que dejes sin cantidad se ignoran.",
    "   • 'Ingreso de productos': lo que PRODUJISTE. Suma al stock del producto y descuenta las materias primas según su receta.",
    "   • 'Compras materias primas': lo que COMPRASTE. Suma al stock de la materia prima. 'costo_total' es opcional.",
    "   • 'Ventas': lo que SALIÓ de productos (vendido). Resta del stock del producto.",
    "   • 'Mermas y regalos': lo que salió SIN venta. Elige el tipo: Merma (pérdida), Regalo o Muestra (entrega de muestra). Elige el ítem de la lista desplegable.",
    "     Los regalos y muestras solo se pueden registrar para productos. Solo las Mermas cuentan para el % de merma.",
    "   • Los productos que COMPARTEN STOCK con otro (por ejemplo 'Torta Retail' o 'Trozo de torta' con 'Torta') no se producen por separado: se produce la Torta; sus ventas van en 'Ventas' y descuentan del stock de la torta.",
    "3. La columna 'fecha' viene con la fecha de hoy. Cámbiala si corresponde (formato 2026-10-14 o 14/10/2026).",
    "4. Para registrar varias veces el mismo producto (por ejemplo en días distintos) copia la fila y cambia la fecha.",
    "5. Cada archivo SUMA movimientos nuevos. No subas dos veces el mismo archivo (la app lo detecta y lo bloquea).",
    "6. Si una fila tiene error (nombre mal escrito, producto sin receta, etc.) NO se carga nada y la app te dice qué corregir.",
    "7. Los nombres no se cambian: son los que existen en la app. Si falta un producto o materia prima, créalo antes (Catálogo).",
    "8. Si el stock del sistema no coincide con lo que realmente tienes, corrígelo en la app, pantalla 'Conteo'.",
]


# ------------------------------------------------------------------ plantilla
def _style_header(ws, headers, widths):
    fill = PatternFill("solid", fgColor="A9583C")
    for j, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = Font(name=_FONT, bold=True, color="FFFFFF")
        c.fill = fill
        ws.column_dimensions[c.column_letter].width = w
    ws.freeze_panes = "A2"


def build_movements_template():
    hoy = date.today()
    wb = Workbook()
    ws0 = wb.active
    ws0.title = "LEEME"
    for i, line in enumerate(LEEME, start=1):
        c = ws0.cell(row=i, column=1, value=line)
        c.font = Font(name=_FONT, size=12 if i == 1 else 10, bold=(i == 1))
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws0.column_dimensions["A"].width = 135

    productos = Product.query.filter_by(activo=True).order_by(Product.nombre).all()
    materias = RawMaterial.query.filter_by(activo=True).order_by(RawMaterial.nombre).all()

    ws = wb.create_sheet(SHEET_PROD)
    _style_header(ws, ["fecha", "producto", "cantidad"], [14, 38, 14])
    for i, p in enumerate([x for x in productos if not x.base_id], start=2):   # las fracciones no se producen
        ws.cell(row=i, column=1, value=hoy).number_format = "yyyy-mm-dd"
        ws.cell(row=i, column=2, value=p.nombre)

    ws = wb.create_sheet(SHEET_BUY)
    _style_header(ws, ["fecha", "materia_prima", "cantidad", "costo_total", "proveedor"], [14, 38, 14, 16, 28])
    for i, m in enumerate(materias, start=2):
        ws.cell(row=i, column=1, value=hoy).number_format = "yyyy-mm-dd"
        ws.cell(row=i, column=2, value=m.nombre)
        ws.cell(row=i, column=5, value=m.proveedor)

    ws = wb.create_sheet(SHEET_SALES)
    _style_header(ws, ["fecha", "producto", "cantidad", "precio"], [14, 38, 14, 14])
    for i, p in enumerate(productos, start=2):
        ws.cell(row=i, column=1, value=hoy).number_format = "yyyy-mm-dd"
        ws.cell(row=i, column=2, value=p.nombre)
        ws.cell(row=i, column=4, value=p.precio_venta)

    # --- hoja de mermas / regalos / muestras, con listas desplegables
    wl = wb.create_sheet("Listas")
    nombres = [p.nombre for p in productos] + [m.nombre for m in materias]
    for i, n in enumerate(nombres, start=1):
        wl.cell(row=i, column=1, value=n)
    for i, t in enumerate(TIPOS_SALIDA, start=1):
        wl.cell(row=i, column=2, value=t)
    for i, mo in enumerate(MOTIVOS_MERMA, start=1):
        wl.cell(row=i, column=3, value=mo)
    wl.sheet_state = "hidden"

    ws = wb.create_sheet(SHEET_WASTE)
    _style_header(ws, ["fecha", "tipo", "producto_o_materia_prima", "cantidad", "motivo", "nota"],
                  [14, 14, 38, 14, 24, 40])
    ex_fill = PatternFill("solid", fgColor="FFF2CC")
    for j, v in enumerate([hoy, "Regalo", "(ejemplo) Brownie", 2, "", "Cliente nuevo"], start=1):
        c = ws.cell(row=2, column=j, value=v)
        c.font = Font(name=_FONT, italic=True)
        c.fill = ex_fill
    ws["A2"].number_format = "yyyy-mm-dd"
    for r in range(3, 63):
        ws.cell(row=r, column=1, value=hoy).number_format = "yyyy-mm-dd"
    dv_tipo = DataValidation(type="list", formula1="=Listas!$B$1:$B$%d" % len(TIPOS_SALIDA), allow_blank=True)
    dv_mot = DataValidation(type="list", formula1="=Listas!$C$1:$C$%d" % len(MOTIVOS_MERMA), allow_blank=True)
    ws.add_data_validation(dv_tipo); ws.add_data_validation(dv_mot)
    dv_tipo.add("B3:B62")
    dv_mot.add("E3:E62")
    if nombres:
        dv_item = DataValidation(type="list", formula1="=Listas!$A$1:$A$%d" % len(nombres), allow_blank=True)
        ws.add_data_validation(dv_item)
        dv_item.add("C3:C62")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# -------------------------------------------------------------------- lectura
def _cell_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"fecha no reconocida: '{s}' (usa por ejemplo 2026-10-14 o 14/10/2026)")


def _n(v, money=False):
    if isinstance(v, bool):
        raise ValueError("número no válido")
    if isinstance(v, (int, float)):
        return float(v)
    return _to_float(v, money=money)


def _blank(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def _rows(wb, sheet, required):
    """[(n_fila, dict)] de la hoja, ignorando filas sin cantidad. Si la hoja
    no existe o no tiene las columnas, devuelve ([], [errores])."""
    if sheet not in wb.sheetnames:
        return [], []
    it = wb[sheet].iter_rows(values_only=True)
    try:
        header = [(str(h).strip().lower().replace(" ", "_") if h is not None else "") for h in next(it)]
    except StopIteration:
        return [], []
    if "costo" in header and "costo_total" not in header:
        header[header.index("costo")] = "costo_total"
    faltan = [c for c in required if c not in header]
    if faltan:
        return [], [f"Hoja '{sheet}': faltan las columnas {', '.join(faltan)}. No cambies los títulos de la fila 1."]
    out = []
    for n, row in enumerate(it, start=2):
        d = dict(zip(header, row))
        if any(str(v or "").strip().lower().startswith("(ejemplo)") for v in d.values()):
            continue
        if _blank(d.get("cantidad")):
            continue
        try:
            if _n(d["cantidad"]) == 0:
                continue
        except ValueError:
            pass  # lo reportará la validación
        out.append((n, d))
    return out, []


# ------------------------------------------------------------------ principal
def import_movements(file_bytes, filename="", allow_duplicate=False):
    """Devuelve dict: ok, errores[], avisos[], resumen{...}, duplicado(opcional)."""
    try:
        wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception:
        return {"ok": False, "errores": ["No pude leer el archivo. Debe ser un Excel (.xlsx) descargado desde la app."], "avisos": []}

    productos = {p.nombre.strip().lower(): p for p in Product.query.all()}
    materias = {m.nombre.strip().lower(): m for m in RawMaterial.query.all()}
    hoy = date.today()
    errores, ops_prod, ops_buy, ops_sales = [], [], [], []

    def chequea_fecha(n, sheet, d):
        if _blank(d.get("fecha")):
            raise ValueError("falta la fecha")
        f = _cell_date(d["fecha"])
        if f > hoy:
            raise ValueError(f"la fecha {f:%d-%m-%Y} está en el futuro")
        return f

    # ---- Ingreso de productos
    filas, errs = _rows(wb, SHEET_PROD, ["fecha", "producto", "cantidad"])
    errores += errs
    for n, d in filas:
        try:
            nombre = str(d["producto"] or "").strip()
            p = productos.get(nombre.lower())
            if p is None:
                raise ValueError(f"el producto '{nombre}' no existe")
            cant = _n(d["cantidad"])
            if cant < 0:
                raise ValueError("la cantidad no puede ser negativa (para corregir usa 'Conteo')")
            if p.base_id:
                raise ValueError(f"'{p.nombre}' comparte el stock de '{p.base.nombre}': no se produce por separado. Registra la producción de '{p.base.nombre}'")
            rec = p.effective_recipe
            if rec is None or not rec.items:
                raise ValueError(f"'{p.nombre}' no tiene receta: sin receta no se pueden descontar materias primas. Cárgala en el catálogo")
            ops_prod.append((p, cant, chequea_fecha(n, SHEET_PROD, d)))
        except ValueError as e:
            errores.append(f"{SHEET_PROD}, fila {n}: {e}")

    # ---- Compras de materias primas
    filas, errs = _rows(wb, SHEET_BUY, ["fecha", "materia_prima", "cantidad"])
    errores += errs
    for n, d in filas:
        try:
            nombre = str(d["materia_prima"] or "").strip()
            m = materias.get(nombre.lower())
            if m is None:
                raise ValueError(f"la materia prima '{nombre}' no existe")
            cant = _n(d["cantidad"])
            if cant < 0:
                raise ValueError("la cantidad no puede ser negativa (para corregir usa 'Conteo')")
            costo = None if _blank(d.get("costo_total")) else _n(d["costo_total"], money=True)
            prov = None if _blank(d.get("proveedor")) else str(d["proveedor"]).strip()
            ops_buy.append((m, cant, costo, prov, chequea_fecha(n, SHEET_BUY, d)))
        except ValueError as e:
            errores.append(f"{SHEET_BUY}, fila {n}: {e}")

    # ---- Ventas
    filas, errs = _rows(wb, SHEET_SALES, ["fecha", "producto", "cantidad"])
    errores += errs
    for n, d in filas:
        try:
            nombre = str(d["producto"] or "").strip()
            p = productos.get(nombre.lower())
            if p is None:
                raise ValueError(f"el producto '{nombre}' no existe")
            cant = _n(d["cantidad"])
            if cant < 0:
                raise ValueError("la cantidad no puede ser negativa (para corregir usa 'Conteo')")
            precio = _n(d["precio"], money=True) if not _blank(d.get("precio")) else (p.precio_venta or 0.0)
            ops_sales.append((p, cant, precio, chequea_fecha(n, SHEET_SALES, d)))
        except ValueError as e:
            errores.append(f"{SHEET_SALES}, fila {n}: {e}")

    # ---- Mermas, regalos y muestras
    ops_waste = []
    filas, errs = _rows(wb, SHEET_WASTE, ["fecha", "tipo", "producto_o_materia_prima", "cantidad"])
    errores += errs
    tipos_ok = {t.lower(): t for t in TIPOS_SALIDA}
    motivos_ok = {m.lower(): m for m in MOTIVOS_MERMA}
    for n, d in filas:
        try:
            tipo = tipos_ok.get(str(d["tipo"] or "").strip().lower())
            if tipo is None:
                raise ValueError(f"tipo '{d['tipo']}' no válido (usa {', '.join(TIPOS_SALIDA)})")
            nombre = str(d["producto_o_materia_prima"] or "").strip()
            p, m = productos.get(nombre.lower()), materias.get(nombre.lower())
            if p is not None and m is not None:
                raise ValueError(f"'{nombre}' existe como producto y como materia prima: renombra uno de los dos")
            if p is None and m is None:
                raise ValueError(f"'{nombre}' no existe como producto ni como materia prima")
            if m is not None and tipo != "Merma":
                raise ValueError(f"los regalos y muestras solo se pueden registrar para productos ('{nombre}' es materia prima)")
            cant = _n(d["cantidad"])
            if cant < 0:
                raise ValueError("la cantidad no puede ser negativa")
            motivo = None
            if tipo == "Merma":
                raw_m = str(d.get("motivo") or "").strip()
                motivo = motivos_ok.get(raw_m.lower()) if raw_m else "Otro"
                if motivo is None:
                    raise ValueError(f"motivo '{raw_m}' no válido (usa {', '.join(MOTIVOS_MERMA)})")
            nota = None if _blank(d.get("nota")) else str(d["nota"]).strip()
            ops_waste.append((("product", p) if p is not None else ("material", m), tipo, cant, motivo, nota,
                              chequea_fecha(n, SHEET_WASTE, d)))
        except ValueError as e:
            errores.append(f"{SHEET_WASTE}, fila {n}: {e}")

    if errores:
        return {"ok": False, "errores": errores, "avisos": [], "resumen": None}
    if not (ops_prod or ops_buy or ops_sales or ops_waste):
        return {"ok": False, "avisos": [], "errores": [
            "El archivo no tiene filas con cantidad. Escribe cantidades en las hojas que correspondan y vuelve a subirlo."]}

    # ---- ¿ya se cargó este mismo contenido? (firma del CONTENIDO, no de los bytes del archivo:
    #      así se detecta aunque el Excel se haya vuelto a guardar)
    firma = "\n".join(sorted(
        [repr(("P", p.id, c, f.isoformat())) for p, c, f in ops_prod]
        + [repr(("B", m.id, c, k, f.isoformat())) for m, c, k, _pv, f in ops_buy]
        + [repr(("S", p.id, c, pr, f.isoformat())) for p, c, pr, f in ops_sales]
        + [repr(("W", k, o.id, t, c, mo, nt, f.isoformat())) for (k, o), t, c, mo, nt, f in ops_waste]
    ))
    sha = hashlib.sha256(firma.encode("utf-8")).hexdigest()
    if not allow_duplicate:
        previo = ImportLog.query.filter_by(sha256=sha).first()
        if previo:
            cuando = previo.creado_en.strftime("%d-%m-%Y %H:%M") if previo.creado_en else "antes"
            return {
                "ok": False, "duplicado": True, "avisos": [],
                "errores": [f"Estos mismos movimientos (mismas fechas, productos y cantidades) ya se cargaron el {cuando} "
                            f"({previo.resumen}). Cargarlos de nuevo duplicaría el stock y los consumos. "
                            "Si de verdad quieres hacerlo, marca 'Cargar de todos modos'."],
            }

    # ---- aplicar TODO en una sola transacción
    try:
        for m, cant, costo, prov, f in ops_buy:
            register_purchase(m.id, cant, costo_total=costo, proveedor=prov or m.proveedor,
                              fecha=f, commit=False)
        for p, cant, f in ops_prod:
            execute_production(product_id=p.id, cantidad_real=cant,
                               fecha=datetime.combine(f, datetime.min.time()), commit=False)
        for p, cant, precio, f in ops_sales:
            register_sale(p.id, cant, precio, canal="Venta directa", fecha=f, commit=False)

        for (kind, obj), tipo, cant, motivo, nota, f in ops_waste:
            register_waste(kind, cant, motivo, product_id=obj.id if kind == "product" else None,
                           raw_material_id=obj.id if kind == "material" else None,
                           fecha=f, tipo=tipo, nota=nota, commit=False)

        resumen_txt = (f"{len(ops_prod)} producciones, {len(ops_buy)} compras, {len(ops_sales)} ventas, "
                       f"{len(ops_waste)} mermas/regalos/muestras")
        db.session.add(ImportLog(sha256=sha, filename=(filename or "")[:255], resumen=resumen_txt))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    # ---- avisos post-carga (no bloquean)
    avisos = []
    st_m = get_all_material_stocks()
    for m in materias.values():
        if m.activo and st_m.get(m.id, 0.0) < -1e-9:
            avisos.append(f"Materia prima '{m.nombre}' quedó en stock NEGATIVO ({st_m[m.id]:g} {m.unidad_medida}): "
                          "faltan compras por cargar o conviene hacer un Conteo.")
    st_p = get_all_product_stocks()
    for p in productos.values():
        if p.activo and st_p.get(p.id, 0.0) < -1e-9:
            avisos.append(f"Producto '{p.nombre}' quedó en stock NEGATIVO ({st_p[p.id]:g}): "
                          "se vendió más de lo producido/registrado. Revisa producción o haz un Conteo.")

    return {
        "ok": True, "errores": [], "avisos": avisos,
        "resumen": {"producciones": len(ops_prod), "compras": len(ops_buy), "ventas": len(ops_sales),
                    "salidas": len(ops_waste)},
    }
