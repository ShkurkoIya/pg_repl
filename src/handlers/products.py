import psycopg
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from rich.table import Table
from rich.panel import Panel
from prompt_toolkit import prompt
from psycopg.rows import class_row

from console import console, render_error
from db import get_conn
from commands import command, CATEGORY_PRODUCTS
from validators import NonEmptyValidator, YesNoValidator, PriceValidator, IntegerValidator


@dataclass
class Product:
    id: int
    sku: str
    name: str
    price: Decimal
    product_category_id: int


def _render_product(product: Product) -> None:
    table = Table(show_header=False, box=None)
    table.add_column("Property", style="bold magenta", width=20)
    table.add_column("Value")

    table.add_row("ID", str(product.id))
    table.add_row("SKU (Артикул)", product.sku)
    table.add_row("Название", product.name)
    table.add_row("Цена", f"{product.price} руб.")
    table.add_row("ID Категории", str(product.product_category_id))

    panel = Panel(table, title=f"Товар: {product.name}", expand=False)
    console.print(panel)


@command("list products", "список всех товаров", CATEGORY_PRODUCTS)
def list_products() -> None:
    conn = get_conn()
    table = Table(title="Каталог товаров", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("SKU (Артикул)", style="green", min_width=15)
    table.add_column("Название товара", style="yellow", min_width=30)
    table.add_column("Цена", style="magenta", justify="right", min_width=12)
    table.add_column("ID Категории", style="blue", justify="center", min_width=12)

    with conn.cursor(row_factory=class_row(Product)) as cur:
        cur.execute("SELECT * FROM catalog.products ORDER BY id")
        products: list[Product] = cur.fetchall()

    if not products:
        console.print("[yellow]⚠ Каталог товаров пуст.[/yellow]")
        return

    for product in products:
        table.add_row(
            str(product.id),
            product.sku,
            product.name,
            f"{product.price:.2f}",
            str(product.product_category_id),
        )
    console.print(table)


@command("show product", "информация о товаре", CATEGORY_PRODUCTS)
def show_product(_id: str) -> None:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Product)) as cur:
        cur.execute("SELECT * FROM catalog.products WHERE id = %s", (_id,))
        product: Product | None = cur.fetchone()

    if product is None:
        render_error(f"Товар с ID {_id} не найден")
        return

    _render_product(product)


@command("add product", "добавить новый товар", CATEGORY_PRODUCTS)
def add_product() -> None:
    conn = get_conn()

    sku = prompt("Введите SKU товара (макс. 30 симв.): ", validator=NonEmptyValidator()).strip()
    name = prompt("Введите название товара: ", validator=NonEmptyValidator()).strip()

    price_input = prompt("Введите цену товара: ", validator=PriceValidator()).strip()
    price = Decimal(price_input)

    cat_input = prompt("Введите ID категории товара: ", validator=IntegerValidator()).strip()
    category_id = int(cat_input)

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO catalog.products (sku, name, price, product_category_id)
               VALUES (%s, %s, %s, %s)""",
            (sku, name, price, category_id),
        )

    console.print(f"[green]✔ Товар '{name}' [dim]({sku})[/dim] успешно добавлен![/green]")


@command("edit product", "редактировать товар", CATEGORY_PRODUCTS)
def edit_product(_id: str) -> None:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Product)) as cur:
        cur.execute("SELECT * FROM catalog.products WHERE id = %s", (_id,))
        product: Product | None = cur.fetchone()

    if product is None:
        render_error(f"Товар с ID {_id} не найден")
        return

    console.print(f"[cyan]Редактирование товара #{_id}. Нажмите Enter для сохранения старого значения.[/cyan]")

    sku = prompt("Новый SKU: ", default=product.sku, validator=NonEmptyValidator()).strip()
    name = prompt("Новое название: ", default=product.name, validator=NonEmptyValidator()).strip()

    price_input = prompt("Новая цена: ", default=str(product.price), validator=PriceValidator()).strip()
    price = Decimal(price_input)

    cat_input = prompt("Новый ID категории: ", default=str(product.product_category_id),
                       validator=IntegerValidator()).strip()
    category_id = int(cat_input)

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

    console.print(f"[green]✔ Товар #{_id} успешно обновлен![/green]")


@command("delete product", "удалить товар", CATEGORY_PRODUCTS)
def delete_product(_id: str) -> None:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Product)) as cur:
        cur.execute("SELECT * FROM catalog.products WHERE id = %s", (_id,))
        product: Product | None = cur.fetchone()

    if product is None:
        render_error(f"Товар с ID {_id} не найден")
        return

    _render_product(product)

    answer = prompt("Вы уверены? (y/n, д/н): ", validator=YesNoValidator()).strip().lower()

    if YesNoValidator.is_yes(answer):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM catalog.products WHERE id = %s", (_id,))
        console.print(f"[green]✔ Товар '{product.name}' успешно удален из каталога![/green]")
    else:
        console.print("[yellow]Удаление отменено.[/yellow]")
