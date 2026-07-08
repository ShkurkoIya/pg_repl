from dataclasses import dataclass
from decimal import Decimal
from psycopg import Connection, Cursor
from psycopg.rows import class_row
from rich.table import Table
from rich.panel import Panel
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog

from console import (
    console,
    render_warning,
    render_prompt_info,
    render_error_panel,
    render_warning_panel,
    render_success_panel
)
from db import get_conn
from commands import command, CATEGORY_PRODUCTS
from validators import NonEmptyValidator, YesNoValidator, PriceValidator

@dataclass
class Product:
    id: int
    sku: str
    name: str
    price: Decimal
    product_category_id: int

def _db_get_product(conn: Connection, _id: int) -> Product | None:
    """Вспомогательная функция для поиска продукта по ID."""
    with conn.cursor(row_factory=class_row(Product)) as cur:
        cur.execute("SELECT * FROM catalog.products WHERE id = %s", (_id,))
        product: Product | None = cur.fetchone()
    return product


def _db_get_all_categories(conn: Connection) -> list[tuple[int, str]]:
    """Вспомогательная функция для получения всех категорий."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM catalog.product_categories ORDER BY name")
        return cur.fetchall()


def _db_get_all_products_with_categories(conn: Connection) -> list:
    """Получить список всех товаров вместе с названиями их категорий."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT p.id, p.sku, p.name, p.price, c.name
            FROM catalog.products AS p
            JOIN catalog.product_categories AS c ON p.product_category_id = c.id
            ORDER BY p.id
        """)
        return cur.fetchall()


def _db_insert_product(conn: Connection, sku: str, name: str, price: Decimal, category_id: int) -> None:
    """Записать новый товар в базу данных."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO catalog.products (sku, name, price, product_category_id)
                VALUES (%s, %s, %s, %s)
                """,
                (sku, name, price, category_id),
            )

def _db_update_product(conn: Connection, _id: int, sku: str, name: str, price: Decimal, category_id: int) -> None:
    """Обновить данные существующего товара в базе данных."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE catalog.products
                   SET sku                 = %s,
                       name                = %s,
                       price               = %s,
                       product_category_id = %s
                   WHERE id = %s""",
                (sku, name, price, category_id, _id),
            )


def _db_delete_product(conn: Connection, _id: int) -> None:
    """Удалить товар из базы данных по его числовому ID."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM catalog.products WHERE id = %s", (_id,))


def _render_product(conn: Connection, product: Product) -> None:
    """Вывести rich карточку одного товара."""
    table = Table(show_header=False, box=None)
    table.add_column("Property", style="bold magenta", width=20)
    table.add_column("Value")

    with conn.cursor() as cur:
        cur.execute("SELECT name FROM catalog.product_categories WHERE id = %s", (product.product_category_id,))
        row = cur.fetchone()
        category_name = row[0] if row else "Неизвестная категория"

    table.add_row("ID", str(product.id))
    table.add_row("SKU (Артикул)", product.sku)
    table.add_row("Название", product.name)
    table.add_row("Цена", f"{product.price} руб.")
    table.add_row("Категория", str(category_name))

    panel = Panel(table, title=f"Товар: {product.name}", expand=False, border_style="cyan")
    console.print(panel)


@command("list products", "список всех товаров", CATEGORY_PRODUCTS)
def list_products() -> None:
    """Вывести таблицу со всеми товарами и их категориями."""
    conn = get_conn()
    table = Table(title="Каталог товаров", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("SKU (Артикул)", style="green", min_width=15)
    table.add_column("Название товара", style="yellow", min_width=30)
    table.add_column("Цена", style="magenta", justify="right", min_width=12)
    table.add_column("Категория", style="blue", justify="center", min_width=12)

    products = _db_get_all_products_with_categories(conn)

    if not products:
        render_warning("Каталог товаров пуст.")
        return

    for p_id, sku, name, price, cat_name in products:
        table.add_row(
            str(p_id),
            sku,
            name,
            f"{Decimal(price):.2f}",
            cat_name,
        )

    console.print(table)


@command("show product", "информация о товаре", CATEGORY_PRODUCTS)
def show_product(_id: int) -> None:
    """Вывести детальную информацию о товаре по его ID."""
    conn = get_conn()
    product = _db_get_product(conn, _id)

    if product is None:
        render_error_panel(f"Товар с ID {_id} не найден")
        return

    _render_product(conn, product)


@command("add product", "добавить новый товар", CATEGORY_PRODUCTS)
def add_product() -> None:
    """Добавить новый товар в каталог с интерактивным выбором категории."""
    conn = get_conn()
    categories = _db_get_all_categories(conn)

    if not categories:
        render_error_panel("Нельзя добавить товар: сначала создайте хотя бы одну категорию!")
        return

    sku = prompt("Введите SKU товара: ", validator=NonEmptyValidator()).strip()
    name = prompt("Введите название товара: ", validator=NonEmptyValidator()).strip()

    price_input = prompt("Введите цену товара: ", validator=PriceValidator()).strip()
    price = Decimal(price_input)

    category_choice = [(cat_id, cat_name) for cat_id, cat_name in categories]

    category_id = radiolist_dialog(
        title="Выбор категории",
        text="Выберите категорию товара из списка (используйте стрелочки и Enter):",
        values=category_choice,
        default=categories[0][0]
    ).run()

    if category_id is None:
        render_warning_panel("Добавление товара отменено.")
        return

    _db_insert_product(conn, sku, name, price, category_id)

    render_success_panel(f"Товар '{name}' ({sku}) успешно добавлен!")

@command("edit product", "редактировать товар", CATEGORY_PRODUCTS)
def edit_product(_id: int) -> None:
    """Редактирование продукта."""
    conn = get_conn()

    categories = _db_get_all_categories(conn)
    if not categories:
        render_error_panel("В базе данных нет категорий!")
        return

    product = _db_get_product(conn, _id)
    if product is None:
        render_error_panel(f"Товар с ID {_id} не найден")
        return

    render_prompt_info(
        f"Редактирование товара #{_id}. Нажмите Enter для сохранения старого значения.\n"
        "       ℹ | Для выхода из режима редактирования категории нажмите ESC на следующем шаге."
    )

    sku = prompt("Новый SKU: ", default=product.sku, validator=NonEmptyValidator()).strip()
    name = prompt("Новое название: ", default=product.name, validator=NonEmptyValidator()).strip()

    price_input = prompt("Новая цена: ", default=str(product.price), validator=PriceValidator()).strip()
    price = Decimal(price_input)

    category_choice = [(c_id, c_name) for c_id, c_name in categories]

    category_id = radiolist_dialog(
        title="Выберите категорию",
        text="Выберите категорию товара из списка (используйте стрелочки и Enter):",
        values=category_choice,
        default=product.product_category_id
    ).run()

    if category_id is None:
        render_warning_panel("Редактирование товара отменено.")
        return

    _db_update_product(conn, _id, sku, name, price, category_id)

    render_success_panel(f"Товар #{_id} успешно обновлен!")



@command("delete product", "удалить товар", CATEGORY_PRODUCTS)
def delete_product(_id: int) -> None:
    """Удалить товар из каталога по его ID с подтверждением."""
    conn = get_conn()
    product = _db_get_product(conn, _id)

    if product is None:
        render_error_panel(f"Товар с ID {_id} не найден")
        return

    _render_product(conn, product)

    render_prompt_info("Внимание! Это действие необратимо.")
    answer = prompt("Вы уверены, что хотите удалить этот товар? (y/n, д/н): ", validator=YesNoValidator()).strip().lower()

    if YesNoValidator.is_yes(answer):
        _db_delete_product(conn, _id)
        render_success_panel(f"Товар '{product.name}' успешно удален из каталога!")
    else:
        render_warning_panel("Удаление товара отменено.")

