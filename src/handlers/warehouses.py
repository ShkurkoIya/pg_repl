from dataclasses import dataclass
from psycopg import Connection
from psycopg.rows import class_row
from rich.panel import Panel
from rich.table import Table
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

from console import (
    console,
    render_warning,
    render_error_panel,
    render_success_panel,
    render_warning_panel,
    render_prompt_info
)
from db import get_conn
from validators import ChoiceValidator, NonEmptyValidator, YesNoValidator
from commands import command, CATEGORY_WAREHOUSES

cities = [
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Челябинск",
    "Самара",
    "Омск",
    "Ростов-на-Дону",
    "Уфа",
    "Красноярск",
    "Воронеж",
    "Пермь",
    "Волгоград",
]

city_completer = WordCompleter(cities, ignore_case=True, sentence=True)
city_validator = ChoiceValidator(
    cities, message="Город должен быть из списка. Используйте Tab для автодополнения."
)


@dataclass
class Warehouse:
    city: str
    address: str
    label: str | None
    is_central: bool
    id: int | None = None


def _db_get_all_warehouses(conn: Connection) -> list[Warehouse]:
    """Получить список всех существующих складов из СУБД."""
    with conn.cursor(row_factory=class_row(Warehouse)) as cur:
        cur.execute("SELECT * FROM catalog.warehouses ORDER BY id")
        return cur.fetchall()


def _db_get_warehouse(conn: Connection, _id: int) -> Warehouse | None:
    """Найти конкретный склад в СУБД по его ID."""
    with conn.cursor(row_factory=class_row(Warehouse)) as cur:
        cur.execute("SELECT * FROM catalog.warehouses WHERE id = %s", (_id,))
        return cur.fetchone()


def _db_add_warehouse(conn: Connection, warehouse: Warehouse) -> int:
    """Добавить склад."""
    with conn.transaction():
        with conn.cursor() as cur:
            if warehouse.is_central:
                cur.execute("""UPDATE catalog.warehouses SET is_central = TRUE WHERE is_central = FALSE;""")

            cur.execute(
                """
                    INSERT INTO catalog.warehouses (city, address, label, is_central) 
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                """, (warehouse.city, warehouse.address, warehouse.label, warehouse.is_central))

            res: tuple[int] | None = cur.fetchone()

            # По идее unreachable, но тайпчекер ругается. Как тут быть?
            if res is None:
                raise RuntimeError(
                    f"Критическая ошибка базы данных: не удалось вернуть ID для склада в городе {warehouse.city}"
                )

            return res[0]


def _db_update_warehouse(conn: Connection, warehouse: Warehouse):
    """Редактирование склада по ID."""
    with conn.transaction():
        with conn.cursor() as cur:
            if warehouse.is_central:
                cur.execute("UPDATE catalog.warehouses SET is_central = FALSE WHERE is_central = TRUE")

            cur.execute(
                """
                    UPDATE catalog.warehouses
                    SET city       = %s,
                        address    = %s,
                        label      = %s,
                        is_central = %s
                    WHERE id = %s
                """,
                (warehouse.city, warehouse.address, warehouse.label, warehouse.is_central, warehouse.id)
            )

            if cur.rowcount == 0:
                raise ValueError(f"Склад с ID {warehouse.id} не найден в базе данных!")


def _render_warehouse(warehouse: Warehouse) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Поле", style="bold cyan", width=15)
    table.add_column("Значение", style="white")

    table.add_row("ID", str(warehouse.id))
    table.add_row("Город", warehouse.city)
    table.add_row("Адрес", warehouse.address)
    table.add_row("Метка", warehouse.label or "")

    central_status = "[bold green]Да (Центральный)[/bold green]" if warehouse.is_central else "[dim]Нет[/dim]"
    table.add_row("Тип склада", central_status)

    panel = Panel(
        table,
        expand=False,
        title=f"[bold green]Склад #{warehouse.id}[/bold green]",
        border_style="green",
    )
    console.print(panel)


@command("list warehouses", "список всех складов", CATEGORY_WAREHOUSES)
def list_warehouses() -> None:
    conn = get_conn()
    table = Table(title="Склады", show_header=True, header_style="bold cyan")

    table.add_column("ID", style="dim", width=6, justify="right")
    table.add_column("Город", style="green", min_width=15)
    table.add_column("Адрес", style="yellow", min_width=25)
    table.add_column("Метка", style="magenta", min_width=15)
    table.add_column("Центральный", style="bold blue", justify="center", width=12)

    warehouses = _db_get_all_warehouses(conn)

    if not warehouses:
        render_warning("Список складов пуст.")
        return

    for warehouse in warehouses:
        table.add_row(
            str(warehouse.id),
            warehouse.city,
            warehouse.address,
            warehouse.label or "",
            "⭐" if warehouse.is_central else "",
        )
    console.print(table)


@command("show warehouse", "информация о складе", CATEGORY_WAREHOUSES)
def show_warehouse(_id: int) -> None:
    conn = get_conn()

    warehouse = _db_get_warehouse(conn, _id)

    if warehouse is None:
        render_error_panel(f"Склад с ID {_id} не найден")
        return

    _render_warehouse(warehouse)


@command("add warehouse", "добавить склад (интерактивно)", CATEGORY_WAREHOUSES)
def add_warehouse() -> None:
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM catalog.warehouses")
        count = cur.fetchone()[0]

    city = prompt("Город: ", validator=city_validator, completer=city_completer).strip()
    address = prompt("Адрес: ", validator=NonEmptyValidator()).strip()
    label = prompt("Метка (необязательно): ").strip() or None

    if count == 0:
        render_warning("Это первый склад. Он автоматически становится ЦЕНТРАЛЬНЫМ.")
        is_central = True
    else:
        is_central_input = prompt("Сделать склад центральным? (y/n): ", validator=YesNoValidator()).strip().lower()
        is_central = YesNoValidator.is_yes(is_central_input)

    new_warehouse = Warehouse(
        city = city,
        address = address,
        label = label,
        is_central = is_central
    )

    _db_add_warehouse(conn, new_warehouse)

    msg_suffix = f" ({label})" if label else ""
    render_success_panel(f"Склад в городе {city}{msg_suffix} добавлен!")


@command("edit warehouse", "редактировать склад", CATEGORY_WAREHOUSES)
def edit_warehouse(_id: int) -> None:
    conn = get_conn()

    editable_wh = _db_get_warehouse(conn, _id)

    if not editable_wh:
        render_error_panel(f"Склад с ID {_id} не найден!")
        return

    console.print(f"[cyan]Редактирование склада #{_id}. Нажмите Enter для сохранения старого значения.[/cyan]")

    city = prompt("Город: ", default=editable_wh.city, validator=city_validator, completer=city_completer).strip()
    address = prompt("Адрес: ", default=editable_wh.address, validator=NonEmptyValidator()).strip()
    label = prompt("Метка (необязательно): ", default=editable_wh.label or "").strip() or None
    is_central = editable_wh.is_central

    if not editable_wh.is_central:
        is_central_input = prompt("Сделать склад центральным? (y/n): ", default="n",
                                  validator=YesNoValidator()).strip().lower()
        is_central = YesNoValidator.is_yes(is_central_input)

    with conn.transaction():
        with conn.cursor() as cur:
            if is_central and not editable_wh.is_central:
                cur.execute("UPDATE catalog.warehouses SET is_central = FALSE WHERE is_central = TRUE")

            updated_warehouse = Warehouse(
                id=_id,
                city=city,
                address=address,
                label=label,
                is_central=is_central
            )

            _db_update_warehouse(conn, updated_warehouse)



    msg_suffix = f" ({label})" if label else ""
    console.print(f"[green]✔ Склад в городе {city}{msg_suffix} обновлен [/green]")


@command("delete warehouse", "удалить склад", CATEGORY_WAREHOUSES)
def delete_warehouse(_id: str) -> None:
    conn = get_conn()

    with conn.cursor(row_factory=class_row(Warehouse)) as cur:
        cur.execute("SELECT * FROM catalog.warehouses WHERE id = %s", (_id,))
        warehouse: Warehouse | None = cur.fetchone()

    if warehouse is None:
        render_error_panel(f"Склад с ID {_id} не найден")
        return

    _render_warehouse(warehouse)

    if warehouse.is_central:
        render_error_panel("Нельзя удалить центральный склад! Сначала назначьте центральным другой склад.")
        return

    answer = prompt("Вы уверены? (y/n, д/н): ", validator=YesNoValidator()).strip().lower()

    if YesNoValidator.is_yes(answer):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM catalog.warehouses WHERE id = %s", (_id,))

        msg_suffix = f" ({warehouse.label})" if warehouse.label else ""
        console.print(f"[green]✔ Склад в городе {warehouse.city}{msg_suffix} удален [/green]")
    else:
        console.print("[yellow]Удаление отменено.[/yellow]")
