# La Gracia — Motor de decisiones

App interna para automatizar ventas, producción, inventario (materia prima,
pre-preparaciones y producto terminado), compras y seguimiento B2B de La
Gracia. Construida como motor de reglas + datos, sin IA compleja, siguiendo
la especificación entregada.

## Cómo correrla

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# cargar datos de ejemplo (opcional, borra y recrea la base de datos)
./venv/bin/python scripts/seed_demo.py

# levantar el servidor
./venv/bin/python app.py
```

Abrir http://127.0.0.1:5050 — esa es la pantalla HOY.

## Estructura

```
la_gracia/
├── app.py                 # app factory de Flask, registra todos los blueprints
├── config.py               # parámetros del motor de reglas (horizontes, umbrales)
├── extensions.py           # instancia compartida de SQLAlchemy
├── models/                 # una tabla por archivo
├── services/                # EL MOTOR DE DECISIONES (la lógica de negocio real)
│   ├── inventory_engine.py      # única fuente de verdad del stock (vía movimientos)
│   ├── costing_engine.py        # costo unitario y margen de productos y preparaciones
│   ├── production_engine.py     # demanda confirmada/probable/esperada y sugerencia de producción
│   ├── preparation_engine.py    # pre-preparaciones: cuánto congelar y ejecución
│   ├── purchasing_engine.py     # punto de reposición, plan de compras, compra hormiga
│   ├── b2b_engine.py             # a quién contactar hoy
│   ├── waste_engine.py           # registro y % de mermas
│   ├── portfolio_engine.py       # diagnóstico GANADOR/POTENCIAL/REVISAR/PAUSADO
│   ├── sales_engine.py           # registrar venta (descuenta stock automáticamente)
│   ├── expiry_engine.py          # alertas de vencimiento (modo simple, sin lotes)
│   ├── import_engine.py          # importación de ventas/compras históricas por CSV
│   └── dashboard_engine.py       # orquesta todo lo anterior para la pantalla HOY
├── routes/                  # blueprints Flask (una fachada delgada sobre los services)
├── templates/                # HTML simple, sin frameworks pesados
├── static/css/style.css      # todo el estilo visual, en un solo archivo
└── scripts/seed_demo.py      # datos de ejemplo (los mismos números del documento)
```

## Principio de arquitectura

Las rutas (`routes/`) NUNCA calculan nada — solo reciben el request, llaman a
un `service`, y renderizan. Toda la lógica de negocio vive en `services/`.
Esto es intencional: permite cambiar Flask por otra tecnología (o exponer
los mismos `services` vía una API para una app móvil, WhatsApp o integración
con TUU) sin tocar la lógica.

## Flujo de inventario (regla fundamental)

Nunca se escribe un campo "stock" directo. Todo pasa por `StockMovement`
(`services/inventory_engine.py`), y el stock siempre se calcula como la
suma de sus movimientos. Esto aplica a materia prima, pre-preparaciones y
producto terminado por igual.

## Flujo de producción con pre-preparación

```
Materia prima → (receta de pre-preparación) → PRE-PREPARACIÓN (congelada)
                                                        ↓
                              (receta de producto: puede usar materia prima
                               Y/O pre-preparación como ingrediente)
                                                        ↓
                                                Producto terminado
```

Ver informe de debilidades para las limitaciones conocidas del control de
vencimiento (modo simple, sin lotes) y otros puntos a revisar.
