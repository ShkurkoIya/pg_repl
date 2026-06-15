from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from psycopg.rows import class_row
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from rich.table import Table
from rich.panel import Panel

from console import console, render_error
from db import get_conn
from commands import command, CATEGORY_SALES
from validators import YesNoValidator, IntegerValidator


@dataclass
class Order:
    id: int
    status: str
    total_amount: Decimal
    created_at: datetime
    warehouse_id: int


@dataclass
class OrderItem:
    id: int
    order_id: int
    product_id: int
    price: Decimal
    quantity: int


def _recalculate_order_total(cur, order_id: int) -> None:
    """Хелпер для автоматического пересчета стоимости заказа в БД"""
    cur.execute(
        "SELECT COALESCE(SUM(price * quantity), 0) FROM sales.order_items WHERE order_id = %s",
        (order_id,)
    )
    new_total = cur.fetchone()[0]
    cur.execute("UPDATE sales.orders SET total_amount = %s WHERE id = %s", (new_total, order_id))


def _check_order_editable(cur, order_id: str) -> Order:
    """Хелпер для проверки существования заказа и блокировки редактирования"""
    cur.row_factory = class_row(Order)

    cur.execute("SELECT * FROM sales.orders WHERE id = %s", (int(order_id),))
    order = cur.fetchone()

    if order is None:
        raise ValueError(f"Заказ с ID {order_id} не найден.")
    if order.status != 'unpublished':
        raise PermissionError(f"Заказ #{order_id} в статусе '{order.status}' нельзя редактировать или удалять!")
    return order


@command("list orders", "список всех заказов", CATEGORY_SALES)
def list_orders() -> None:
    conn = get_conn()
    table = Table(title="Каталог заказов", show_header=True, header_style="bold cyan")
    table.add_column("ID", justify="right", width=6)
    table.add_column("Статус", style="yellow", min_width=15)
    table.add_column("Общая сумма", style="green", justify="right", min_width=12)
    table.add_column("Дата создания", style="magenta", min_width=20)
    table.add_column("ID Склада", justify="center")

    with conn.cursor(row_factory=class_row(Order)) as cur:
        cur.execute("SELECT * FROM sales.orders ORDER BY id DESC")
        orders = cur.fetchall()

    if not orders:
        console.print("[yellow]⚠ Список заказов пуст.[/yellow]")
        return

    for order in orders:
        table.add_row(
            str(order.id), order.status, f"{order.total_amount:.2f}",
            order.created_at.strftime("%Y-%m-%d %H:%M:%S"), str(order.warehouse_id)
        )
    console.print(table)


@command("show order", "детальная информация о заказе", CATEGORY_SALES)
def show_order(_id: str) -> None:
    conn = get_conn()
    with conn.cursor(row_factory=class_row(Order)) as cur:
        cur.execute("SELECT * FROM sales.orders WHERE id = %s", (int(_id),))
        order = cur.fetchone()

    if order is None:
        render_error(f"Заказ с ID {_id} не найден")
        return

    with conn.cursor() as cur:
        cur.execute(
            """SELECT oi.price, oi.quantity, p.name as product_name
               FROM sales.order_items oi
                        JOIN catalog.products p ON oi.product_id = p.id
               WHERE oi.order_id = %s""", (int(_id),)
        )
        items = cur.fetchall()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("ID Заказа", str(order.id))
    table.add_row("Статус", f"[bold yellow]{order.status}[/bold yellow]")
    table.add_row("Сумма заказа", f"[bold green]{order.total_amount:.2f} руб.[/bold green]")
    table.add_row("Дата создания", order.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("ID Склада", str(order.warehouse_id))
    console.print(Panel(table, title=f"Заказ #{order.id}", expand=False, border_style="blue"))

    if items:
        it = Table(title="Состав заказа", show_header=True, header_style="bold magenta")
        it.add_column("Товар")
        it.add_column("Цена", justify="right")
        it.add_column("Количество", justify="center")
        it.add_column("Стоимость", justify="right")
        for item in items:
            price = Decimal(item[0])
            qty = int(item[1])
            prod_name = item[2]
            it.add_row(prod_name, f"{price:.2f}", str(qty), f"{(price * qty):.2f}")
        console.print(it)


@command("add order", "создать новый заказ (интерактивно)", CATEGORY_SALES)
def add_order() -> None:
    conn = get_conn()
    wh_id_input = prompt("Введите ID склада отгрузки: ", validator=IntegerValidator()).strip()
    warehouse_id = int(wh_id_input)

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM catalog.warehouses WHERE id = %s", (warehouse_id,))
            if not cur.fetchone():
                render_error(f"Склад с ID {warehouse_id} не существует!")
                return
            cur.execute("INSERT INTO sales.orders (warehouse_id) VALUES (%s) RETURNING id", (warehouse_id,))
            order_id = cur.fetchone()[0]

    console.print(f"[green]✔ Создан черновик заказа #{order_id} (status: unpublished)[/green]")

    add_order_item(str(order_id), interactive=True)


@command("add order_item", "добавить товар в заказ", CATEGORY_SALES)
def add_order_item(order_id: str, interactive: bool = False) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        try:
            _check_order_editable(cur, order_id)
        except (ValueError, PermissionError) as e:
            render_error(str(e))
            return

    while True:
        with conn.cursor() as cur:
            cur.execute("SELECT product_id FROM sales.order_items WHERE order_id = %s", (int(order_id),))
            exclude_ids = [r[0] for r in cur.fetchall()]

            if exclude_ids:
                cur.execute("SELECT id, name, price FROM catalog.products WHERE id NOT IN %s ORDER BY name",
                            (tuple(exclude_ids),))
            else:
                cur.execute("SELECT id, name, price FROM catalog.products ORDER BY name")
            products = cur.fetchall()

        if not products:
            console.print("[yellow]Все доступные товары уже добавлены в заказ.[/yellow]")
            break

        prod_map = {p[1]: {"id": p[0], "price": Decimal(p[2])} for p in products}
        completer = WordCompleter(list(prod_map.keys()), ignore_case=True, sentence=True)

        console.print("[cyan]Выберите товар (Используйте Tab):[/cyan]")
        name_input = prompt("Товар: ", completer=completer).strip()

        if name_input not in prod_map:
            console.print("[bold red]Ошибка: Выберите строго из списка![/bold red]")
            continue

        selected = prod_map[name_input]
        qty = int(prompt("Количество: ", validator=IntegerValidator()).strip())

        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sales.order_items (order_id, product_id, price, quantity) VALUES (%s, %s, %s, %s)",
                    (int(order_id), selected["id"], selected["price"], qty)
                )
                _recalculate_order_total(cur, int(order_id))

        console.print(f"[green]✔ '{name_input}' успешно добавлен.[/green]")

        if not interactive:
            break

        ans = prompt("Добавить ещё товар? (y/n): ", validator=YesNoValidator()).strip().lower()
        if not YesNoValidator.is_yes(ans):
            break


@command("publish order", "опубликовать заказ (перевод в статус new)", CATEGORY_SALES)
def publish_order(order_id: str) -> None:
    conn = get_conn()
    with conn.transaction():
        with conn.cursor() as cur:
            try:
                _check_order_editable(cur, order_id)
            except (ValueError, PermissionError) as e:
                render_error(str(e))
                return

            cur.execute("UPDATE sales.orders SET status = 'new' WHERE id = %s", (int(order_id),))
    console.print(
        f"[green]✔ Заказ #{order_id} успешно опубликован в статус 'new'. Редактирование заблокировано.[/green]")


@command("delete order", "удалить заказ", CATEGORY_SALES)
def delete_order(order_id: str) -> None:
    conn = get_conn()
    with conn.transaction():
        with conn.cursor() as cur:
            try:
                _check_order_editable(cur, order_id)
            except (ValueError, PermissionError) as e:
                render_error(str(e))
                return

            cur.execute("DELETE FROM sales.orders WHERE id = %s", (int(order_id),))
    console.print(f"[green]✔ Заказ #{order_id} и все его позиции успешно удалены.[/green]")
