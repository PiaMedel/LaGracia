"""
Carga datos de ejemplo que replican los números usados en el documento de
especificación (secciones 4, 6, 9, 13, 15, 17, 18 y 19), para poder probar
que el motor de reglas calcula lo que el documento espera.

Uso: python scripts/seed_demo.py
"""
import sys
import os
from datetime import date, timedelta, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models.products import Product
from models.raw_materials import RawMaterial
from models.recipes import Recipe, RecipeItem
from models.preparations import Preparation, PreparationRecipe, PreparationRecipeItem
from models.customers import Customer
from models.orders import Order, OrderItem
from services.inventory_engine import registrar_movimiento
from services.sales_engine import register_sale

app = create_app()

with app.app_context():
    # limpiar todo para poder correr el script varias veces
    db.drop_all()
    db.create_all()

    # ---------------- Materias primas (sección 7 y ejemplo sección 17/18) ----------------
    harina = RawMaterial(nombre="Harina almendras", unidad_medida="kg",
                          stock_seguridad=2, consumo_diario_estimado=2,
                          dias_reposicion=3, compra_minima=10, costo_unitario=6000,
                          proveedor="Proveedor A", vida_util_dias=180)
    cacao = RawMaterial(nombre="Cacao", unidad_medida="kg",
                         stock_seguridad=1, consumo_diario_estimado=0.5,
                         dias_reposicion=5, compra_minima=5, costo_unitario=8000,
                         proveedor="Proveedor B")
    eritritol = RawMaterial(nombre="Eritritol", unidad_medida="kg",
                             stock_seguridad=1, consumo_diario_estimado=0.4,
                             dias_reposicion=4, compra_minima=3, costo_unitario=5000,
                             proveedor="Proveedor A")
    huevos = RawMaterial(nombre="Huevos", unidad_medida="un",
                          stock_seguridad=12, consumo_diario_estimado=10,
                          dias_reposicion=2, compra_minima=30, costo_unitario=200,
                          proveedor="Proveedor C", vida_util_dias=21)
    mantequilla = RawMaterial(nombre="Mantequilla", unidad_medida="kg",
                               stock_seguridad=1, consumo_diario_estimado=0.6,
                               dias_reposicion=3, compra_minima=5, costo_unitario=7000,
                               proveedor="Proveedor B")
    chocolate = RawMaterial(nombre="Chocolate", unidad_medida="kg",
                             stock_seguridad=1, consumo_diario_estimado=0.8,
                             dias_reposicion=4, compra_minima=5, costo_unitario=9000,
                             proveedor="Proveedor B")
    harina_coco = RawMaterial(nombre="Harina de coco", unidad_medida="kg",
                               stock_seguridad=1, consumo_diario_estimado=0.3,
                               dias_reposicion=4, compra_minima=5, costo_unitario=5500,
                               proveedor="Proveedor A")

    db.session.add_all([harina, cacao, eritritol, huevos, mantequilla, chocolate, harina_coco])
    db.session.flush()

    # stock inicial de materias primas (harina almendras: 2kg, según ejemplo sección 17)
    registrar_movimiento("material", harina.id, 2, "stock_inicial", commit=False)
    registrar_movimiento("material", cacao.id, 5, "stock_inicial", commit=False)
    registrar_movimiento("material", eritritol.id, 1, "stock_inicial", commit=False)
    registrar_movimiento("material", huevos.id, 24, "stock_inicial", fecha=datetime.combine(date.today() - timedelta(days=18), datetime.min.time()), commit=False)
    registrar_movimiento("material", mantequilla.id, 3, "stock_inicial", commit=False)
    registrar_movimiento("material", chocolate.id, 4, "stock_inicial", commit=False)
    registrar_movimiento("material", harina_coco.id, 2, "stock_inicial", commit=False)
    db.session.commit()

    # ---------------- Productos (sección 4, 6) ----------------
    brownie = Product(nombre="Brownie", categoria="Bizcochería", unidad_venta="unidad",
                       precio_venta=4000, estado="GANADOR", stock_seguridad=5, vida_util_dias=5)
    galletas = Product(nombre="Galletas", categoria="Galletería", unidad_venta="unidad",
                        precio_venta=1500, estado="POTENCIAL", stock_seguridad=6, vida_util_dias=10)
    torta = Product(nombre="Torta chocolate", categoria="Tortas", unidad_venta="unidad",
                     precio_venta=25000, estado="REVISAR", stock_seguridad=1, vida_util_dias=4)
    db.session.add_all([brownie, galletas, torta])
    db.session.flush()

    # stock inicial de productos terminados (Brownie: 8, según sección 4)
    registrar_movimiento("product", brownie.id, 8, "stock_inicial", commit=False)
    registrar_movimiento("product", galletas.id, 12, "stock_inicial", commit=False)
    registrar_movimiento("product", torta.id, 1, "stock_inicial", commit=False)
    db.session.commit()

    # ---------------- Pre-preparación de ejemplo (nueva sección: masa base congelada) ----------------
    masa_base_brownie = Preparation(
        nombre="Masa base brownie", unidad_medida="porción",
        stock_seguridad=6,
        vida_util_congelada_dias=90,      # 90 días en el congelador
        vida_util_descongelada_dias=2,    # 2 días una vez descongelada
    )
    db.session.add(masa_base_brownie)
    db.session.flush()

    prep_recipe = PreparationRecipe(preparation_id=masa_base_brownie.id, rendimiento=12)  # rinde 12 porciones (1 tanda de brownies)
    db.session.add(prep_recipe)
    db.session.flush()
    db.session.add_all([
        PreparationRecipeItem(recipe_id=prep_recipe.id, raw_material_id=cacao.id, cantidad=0.100),
        PreparationRecipeItem(recipe_id=prep_recipe.id, raw_material_id=eritritol.id, cantidad=0.080),
        PreparationRecipeItem(recipe_id=prep_recipe.id, raw_material_id=mantequilla.id, cantidad=0.150),
    ])
    db.session.commit()

    # stock inicial de la preparación: ya hay 12 porciones (1 tanda) pre-preparadas y congeladas
    registrar_movimiento("preparation", masa_base_brownie.id, 12, "stock_inicial", commit=False)
    db.session.commit()

    # ---------------- Recetas (sección 9: Brownie rinde 12) ----------------
    # Ahora la receta del Brownie usa materias primas DIRECTAS (harina, huevos,
    # chocolate) Y la pre-preparación "Masa base brownie" (cacao+eritritol+
    # mantequilla ya congelados). Esto demuestra la cascada de 2 niveles:
    # materia prima -> pre-preparación -> producto final.
    recipe_brownie = Recipe(product_id=brownie.id, rendimiento=12)
    db.session.add(recipe_brownie)
    db.session.flush()
    db.session.add_all([
        RecipeItem(recipe_id=recipe_brownie.id, ingredient_type="material",
                   raw_material_id=harina.id, cantidad=0.300),
        RecipeItem(recipe_id=recipe_brownie.id, ingredient_type="material",
                   raw_material_id=huevos.id, cantidad=4),
        RecipeItem(recipe_id=recipe_brownie.id, ingredient_type="material",
                   raw_material_id=chocolate.id, cantidad=0.200),
        RecipeItem(recipe_id=recipe_brownie.id, ingredient_type="preparation",
                   preparation_id=masa_base_brownie.id, cantidad=12),  # 12 porciones = 1 tanda de masa
    ])

    recipe_galletas = Recipe(product_id=galletas.id, rendimiento=20)
    db.session.add(recipe_galletas)
    db.session.flush()
    db.session.add_all([
        RecipeItem(recipe_id=recipe_galletas.id, ingredient_type="material", raw_material_id=harina_coco.id, cantidad=0.400),
        RecipeItem(recipe_id=recipe_galletas.id, ingredient_type="material", raw_material_id=eritritol.id, cantidad=0.150),
        RecipeItem(recipe_id=recipe_galletas.id, ingredient_type="material", raw_material_id=mantequilla.id, cantidad=0.200),
        RecipeItem(recipe_id=recipe_galletas.id, ingredient_type="material", raw_material_id=huevos.id, cantidad=2),
    ])
    db.session.commit()
    # Torta chocolate se deja sin receta a propósito, para probar el caso
    # "producto sin costo configurado" en el diagnóstico de portafolio.

    # ---------------- Cliente B2B (sección 13: Cafetería X, frecuencia 7 días, últ. pedido jueves 3, prom. 30) ----------------
    cafeteria_x = Customer(
        nombre="Cafetería X", tipo="Cafetería", contacto="Juan Pérez",
        whatsapp="56912345678", estado="Activo",
        frecuencia_habitual_dias=7, dia_habitual="Jueves",
        ultimo_pedido=date.today() - timedelta(days=7),  # simula "hoy corresponde"
        cantidad_promedio=30, precio_acordado=3500,
        producto_habitual_id=brownie.id,
    )
    hotel_y = Customer(
        nombre="Hotel Y", tipo="Hotel", contacto="Recepción",
        whatsapp="56987654321", estado="Activo",
        frecuencia_habitual_dias=14, dia_habitual="Lunes",
        ultimo_pedido=date.today() - timedelta(days=20),  # atrasado
        cantidad_promedio=15, precio_acordado=3800,
        producto_habitual_id=brownie.id,
    )
    tienda_z = Customer(
        nombre="Tienda Z", tipo="Tienda", contacto="Marcela",
        whatsapp="56911112222", estado="Activo",
        frecuencia_habitual_dias=10, dia_habitual="Miércoles",
        ultimo_pedido=date.today() - timedelta(days=2),  # todavía no corresponde
        cantidad_promedio=20, precio_acordado=1300,
        producto_habitual_id=galletas.id,
    )
    db.session.add_all([cafeteria_x, hotel_y, tienda_z])
    db.session.commit()

    # ---------------- Pedido confirmado (sección 15: 15 brownies confirmados) ----------------
    pedido = Order(
        tipo="Pedido B2B", customer_id=cafeteria_x.id,
        fecha_entrega=date.today() + timedelta(days=1),
        estado="Confirmado",
    )
    db.session.add(pedido)
    db.session.flush()
    db.session.add(OrderItem(order_id=pedido.id, product_id=brownie.id, cantidad=15, precio=3500))
    db.session.commit()

    # ---------------- Historial de ventas (para calcular demanda base y ranking) ----------------
    for i in range(1, 11):
        register_sale(brownie.id, cantidad=6, precio=4000, canal="Venta directa",
                      fecha=date.today() - timedelta(days=i))
    for i in range(1, 6):
        register_sale(galletas.id, cantidad=4, precio=1500, canal="Instagram",
                      fecha=date.today() - timedelta(days=i * 2))
    # Torta chocolate: sin ventas recientes -> debería sugerirse PAUSADO en portafolio

    # Nota de datos de ejemplo: las ventas históricas de arriba, sin producción
    # histórica que las respalde, dejarían el stock actual en negativo (se
    # vendió más de lo que había). Para que el stock actual coincida con el
    # ejemplo del documento (sección 4: Brownie=8, Galletas=12), agregamos acá
    # la producción histórica equivalente que en la realidad sí ocurrió.
    for i in range(1, 11):
        registrar_movimiento("product", brownie.id, 6, "produccion_entrada",
                              referencia_tipo="manual_seed",
                              fecha=datetime.combine(date.today() - timedelta(days=i), datetime.min.time()),
                              commit=False)
    for i in range(1, 6):
        registrar_movimiento("product", galletas.id, 4, "produccion_entrada",
                              referencia_tipo="manual_seed",
                              fecha=datetime.combine(date.today() - timedelta(days=i * 2), datetime.min.time()),
                              commit=False)
    db.session.commit()

    print("Datos de ejemplo cargados correctamente.")
