from dataclasses import dataclass
from datetime import datetime
from psycopg import Connection
from psycopg.rows import class_row
from psycopg import Cursor
from console import (
    console,
    render_warning,
    render_error_panel,
    render_success_panel,
    render_info_panel,
    render_warning_panel,
    render_prompt_info
)
from rich.table import Table
from rich.panel import Panel
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog
from decimal import Decimal
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
    order_id: int
    product_id: int
    price: Decimal
    quantity: int


def _recalculate_order_total(cur: Cursor, order_id: int) -> None:
    """Хелпер для автоматического пересчета стоимости заказа в БД."""
    cur.execute(
        "SELECT COALESCE(SUM(price * quantity), 0) FROM sales.order_items WHERE order_id = %s",
        (order_id,)
    )

    (new_total,) = cur.fetchone()

    cur.execute("UPDATE sales.orders SET total_amount = %s WHERE id = %s", (new_total, order_id))


def _db_get_order_with_warehouse(conn: Connection, order_id: int) -> tuple | None:
    """Получить данные заказа вместе с названием склада."""
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT o.id, o.status, o.total_amount, o.created_at, w.name
                    FROM sales.orders AS o
                             JOIN catalog.warehouses AS w ON o.warehouse_id = w.id
                    WHERE o.id = %s
                    """, (order_id,))
        return cur.fetchone()


def _db_get_order_items(conn: Connection, order_id: int) -> list:
    """Получить все позиции конкретного заказа."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT oi.price, oi.quantity, p.name AS product_name
            FROM sales.order_items oi
                JOIN catalog.products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """, (order_id,))
        return cur.fetchall()


def _db_create_order(conn: Connection, warehouse_id: int) -> int:
    """Создать новый заказ и венуть его ID."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sales.orders (warehouse_id) VALUES (%s) RETURNING id",
                (warehouse_id,)
            )
            (order_id,) = cur.fetchone()
            return order_id


def _db_upsert_order_item(conn: Connection, order_id: int, product_id: int, price: Decimal, quantity: int) -> None:
    """Добавить или обновить позицию товара в заказе (UPSERT) с пересчетом суммы."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
            """
                INSERT INTO sales.order_items (order_id, product_id, price, quantity)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (order_id, product_id)
                    DO UPDATE SET quantity = sales.order_items.quantity + EXCLUDED.quantity
            """, (order_id, product_id, price, quantity))
            _recalculate_order_total(cur, order_id)


def _check_order_editable(cur: Cursor, order_id: int) -> Order:
    """Хелпер для проверки существования заказа и блокировки редактирования"""

    order: Order | None = None

    with cur.connection.cursor(row_factory=class_row(Order)) as check_cur:
        check_cur.execute("SELECT * FROM sales.orders WHERE id = %s", (order_id,))
        order = check_cur.fetchone()

    if order is None:
        raise ValueError(f"Заказ с ID {order_id} не найден.")
    if order.status != 'unpublished':
        raise PermissionError(f"Заказ #{order_id} в статусе '{order.status}' нельзя редактировать или удалять!")
    return order


@command("show order", "детальная информация о заказе", CATEGORY_SALES)
def show_order(_id: int) -> None:
    """Вывести детальную карточку заказа и список всех его позиций."""
    conn = get_conn()

    order_row = _db_get_order_with_warehouse(conn, _id)
    if order_row is None:
        render_error_panel(f"Заказ с ID {_id} не найден")
        return

    o_id, status, total_amount, created_at, wh_name = order_row
    items = _db_get_order_items(conn, o_id)

    # Отрисовка карточки
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("ID Заказа", str(o_id))
    table.add_row("Статус", f"[bold yellow]{status}[/bold yellow]")
    table.add_row("Сумма заказа", f"[bold green]{Decimal(total_amount):.2f} руб.[/bold green]")
    table.add_row("Дата создания", created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "-")
    table.add_row("Склад назначения", wh_name)
    console.print(Panel(table, title=f"Заказ #{o_id}", expand=False, border_style="blue"))

    # Отрисовка состава
    if items:
        it = Table(title="Состав заказа", show_header=True, header_style="bold magenta")
        it.add_column("Товар")
        it.add_column("Цена", justify="right")
        it.add_column("Количество", justify="center")
        it.add_column("Стоимость", justify="right")

        for price, qty, prod_name in items:
            price_dec = Decimal(price)
            qty_int = int(qty)
            it.add_row(prod_name, f"{price_dec:.2f}", str(qty_int), f"{(price_dec * qty_int):.2f}")
        console.print(it)


@command("add order", "создать новый заказ (интерактивно)", CATEGORY_SALES)
def add_order() -> None:
    """Создать новый заказ с интерактивным выбором склада."""
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute(
        """
            SELECT id,
                CASE
                    WHEN label IS NOT NULL AND length(trim(label)) > 0
                    THEN label || ' (' || city || ', ' || address || ')'
                    ELSE city || ', ' || address
                END AS wh_display_name
            FROM catalog.warehouses
            ORDER BY city
        """)
        warehouses = cur.fetchall()

    if not warehouses:
        render_error_panel("Нельзя создать заказ: сначала создайте хотя бы один склад!")
        return

    warehouses_choice = [(wh_id, wh_name) for wh_id, wh_name in warehouses]

    warehouse_id = radiolist_dialog(
        title="Выбор склада отгрузки",
        text="Выберите склад, с которого будет производиться отгрузка заказа:",
        values=warehouses_choice,
    ).run()

    if warehouse_id is None:
        render_warning_panel("Создание заказа отменено.")
        return

    order_id = _db_create_order(conn, warehouse_id)

    render_success_panel(f"Создан заказ #{order_id} (статус: unpublished)")

    _interactive_add_items(order_id)


@command("add order_item", "добавить товар в заказ", CATEGORY_SALES)
def add_order_item(order_id: int) -> bool:
    """Добавить товар в заказ."""
    conn = get_conn()

    with conn.cursor() as cur:
        try:
            _check_order_editable(cur, order_id)
        except (ValueError, PermissionError) as e:
            render_error_panel(str(e))
            return False

    with conn.cursor() as cur:
        cur.execute("SELECT id, name, price FROM catalog.products ORDER BY name")
        products = cur.fetchall()

    if not products:
        render_error_panel("В каталоге товаров пусто! Нечего добавлять.")
        return False

    product_choices = [
        ({"id": p_id, "name": p_name, "price": Decimal(p_price)}, f"{p_name} ({p_price:.2f} руб.)")
        for p_id, p_name, p_price in products
    ]

    selected_product = radiolist_dialog(
        title=f"Добавление в заказ #{order_id}",
        text="Выберите товар из списка (или нажмите ESC для отмены):",
        values=product_choices,
    ).run()

    if selected_product is None:
        render_warning_panel("Добавление товара отменено.")
        return False

    selected_product: dict = selected_product

    p_id = int(selected_product["id"])
    prod_price = selected_product["price"]

    qty = int(prompt("Введите количество товара: ", validator=IntegerValidator()).strip())

    _db_upsert_order_item(conn, order_id, p_id, prod_price, qty)

    render_success_panel(f"Товар '{selected_product['name']}' (x{qty}) успешно добавлен/обновлен в заказе #{order_id}!")
    return True


def _interactive_add_items(order_id: int) -> None:
    """Вспомогательная обертка для циклического добавления товаров в заказ."""
    while True:
        if not add_order_item(order_id):
            break

        render_prompt_info("Хотите добавить в этот заказ еще один товар?")
        ans = prompt("Продолжить добавление позиций? (y/n): ", validator=YesNoValidator()).strip().lower()

        if not YesNoValidator.is_yes(ans):
            break

    render_info_panel(f"Формирование позиций заказа #{order_id} успешно завершено.")


@command("list orders", "список всех заказов", CATEGORY_SALES)
def list_orders() -> None:
    """Вывести таблицу со всеми заказами и названиями их складов."""
    conn = get_conn()
    table = Table(title="Каталог заказов", show_header=True, header_style="bold cyan")

    table.add_column("ID", justify="right", width=6)
    table.add_column("Статус", style="yellow", min_width=15)
    table.add_column("Общая сумма", style="green", justify="right", min_width=12)
    table.add_column("Дата создания", style="magenta", min_width=20)
    table.add_column("Склад назначения", style="blue", min_width=20)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT o.id, o.status, o.total_amount, o.created_at, w.name
            FROM sales.orders AS o
                JOIN catalog.warehouses AS w ON o.warehouse_id = w.id
            ORDER BY o.id DESC
        """)
        orders = cur.fetchall()

    if not orders:
        render_warning("Список заказов пуст.")
        return

    for o_id, status, total_amount, created_at, wh_name in orders:
        table.add_row(
            str(o_id),
            status,
            f"{Decimal(total_amount):.2f}",
            created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "-",
            wh_name
        )

    console.print(table)


@command("publish order", "опубликовать заказ (перевод в статус new)", CATEGORY_SALES)
def publish_order(order_id: int) -> None:
    """Опубликовать заказ, переведя его в статус 'new' и заблокировав для изменений."""
    conn = get_conn()
    with conn.transaction():
        with conn.cursor() as cur:
            try:
                _check_order_editable(cur, order_id)
            except (ValueError, PermissionError) as e:
                render_error_panel(str(e))
                return

            cur.execute("UPDATE sales.orders SET status = 'new' WHERE id = %s", (order_id,))

    render_success_panel(f"Заказ #{order_id} успешно опубликован в статус 'new'. Редактирование заблокировано.")


@command("delete order", "удалить заказ", CATEGORY_SALES)
def delete_order(order_id: int) -> None:
    """Удалить черновик заказа и все связанные с ним позиции из базы данных."""
    conn = get_conn()
    with conn.transaction():
        with conn.cursor() as cur:
            try:
                _check_order_editable(cur, order_id)
            except (ValueError, PermissionError) as e:
                render_error_panel(str(e))
                return

            cur.execute("DELETE FROM sales.orders WHERE id = %s", (order_id,))

    render_success_panel(f"Заказ #{order_id} и все его позиции успешно удалены.")
