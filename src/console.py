from enum import Enum
from rich.console import Console
from rich.panel import Panel

# Rich console object. https://rich.readthedocs.io/en/latest/console.html.
console = Console()


class MessageType(Enum):
    """Перечисление всех возможных типов уведомлений и их стилей"""
    ERROR = ("red", "❌", "Ошибка")
    SUCCESS = ("green", "✔", "Успех")
    WARNING = ("yellow", "⚠", "Предупреждение")
    INFO = ("blue", "ℹ", "Инфо")
    PROMPT = ("cyan", "ℹ", None)

def render_message(message: str, type_: MessageType, as_panel: bool = True) -> None:
    """ Универсальный метод для вывода любых уведомлений в системе.

        :param message: Текст сообщения.
        :param type_: Тип сообщения из Enum MessageType.
        :param as_panel: True - Вывести рамкой
                         False - вывести строчкой
    """
    color, icon, title = type_.value

    if as_panel:
        panel = Panel(
            f"[bold]{color}] {icon} | {message}[/bold {color}]",
            expand=False,
            title=f"[bold{color}]{title}[/bold {color}]",
            border_style=color,
        )
        console.print(panel)
    else:
        console.print(f"[{color}] {icon} | {message}[/{color}]")


# ═════════════════════════════════════════════════════════════════════════
# ШОРТКАТЫ ДЛЯ ТЕКСТА
# ═════════════════════════════════════════════════════════════════════════

def render_error(message: str) -> None:
    """Вывести ошибку строкой текста."""
    render_message(message, MessageType.ERROR, as_panel=False)


def render_success(message: str) -> None:
    """Вывести успех строкой текста."""
    render_message(message, MessageType.SUCCESS, as_panel=False)


def render_warning(message: str) -> None:
    """Вывести предупреждение строкой текста."""
    render_message(message, MessageType.WARNING, as_panel=False)


def render_info(message: str) -> None:
    """Вывести информацию строкой текста."""
    render_message(message, MessageType.INFO, as_panel=False)


def render_prompt_info(message: str) -> None:
    """Вывести подсказку к вводу строкой текста."""
    render_message(message, MessageType.PROMPT, as_panel=False)


# ═════════════════════════════════════════════════════════════════════════
# ШОРТКАТЫ ДЛЯ ТЕКСТА
# ═════════════════════════════════════════════════════════════════════════

def render_error_panel(message: str) -> None:
    """Вывести ошибку в панели."""
    render_message(message, MessageType.ERROR, as_panel=True)


def render_success_panel(message: str) -> None:
    """Вывести успех в панели."""
    render_message(message, MessageType.SUCCESS, as_panel=True)


def render_warning_panel(message: str) -> None:
    """Вывести предупреждение в панели."""
    render_message(message, MessageType.WARNING, as_panel=True)


def render_info_panel(message: str) -> None:
    """Вывести информацию в панели."""
    render_message(message, MessageType.INFO, as_panel=True)


