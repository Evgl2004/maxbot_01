"""
Клавиатуры для системы модерации
==================================
Содержат класс ModerationKeyboard со статическими методами,
создающими inline-клавиатуры для модераторов:
- главное меню модератора
- список тикетов с пагинацией и фильтрами
- детальный просмотр тикета с действиями
- ответ на тикет
- кнопки после ответа
- возврат в главное меню
"""

from typing import List
from datetime import datetime, timezone

from maxapi.types import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from app.database.models import Ticket


class ModerationKeyboard:
    """
    Клавиатуры для модераторов.
    Все методы возвращают готовую inline-клавиатуру (объект вложения).
    """

    @staticmethod
    def main_menu():
        """
        Главное меню модератора.

        Кнопки:
        - «📋 Все тикеты» – без фильтра.
        - «🆕 Новые тикеты» – статус 'open'.
        - «🔄 В работе» – статус 'in_progress'.

        Returns:
            InlineKeyboardMarkup: клавиатура.
        """
        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="📋 Все тикеты", payload="mod_tickets_all")
        )
        builder.row(
            CallbackButton(text="🆕 Новые тикеты", payload="mod_tickets_open")
        )
        builder.row(
            CallbackButton(text="🔄 В работе", payload="mod_tickets_progress")
        )
        return builder.as_markup()

    @staticmethod
    def tickets_list(
        tickets: List[Ticket],
        current_page: int = 1,
        total_pages: int = 1,
        filter_key: str = 'all'
    ):
        """
        Список тикетов с пагинацией.

        Для каждого тикета создаётся кнопка с эмодзи статуса, номером,
        именем пользователя и временем. Внизу – кнопки навигации и возврата.

        Args:
            tickets (List[Ticket]): тикеты на текущей странице.
            current_page (int): номер текущей страницы.
            total_pages (int): общее количество страниц.
            filter_key (str): идентификатор фильтра ('all', 'open', 'progress').

        Returns:
            InlineKeyboardMarkup: клавиатура.
        """
        builder = InlineKeyboardBuilder()

        # Кнопки для каждого тикета
        for ticket in tickets:
            status_emoji = {
                "open": "🆕",
                "in_progress": "🔄",
                "closed": "🔒"
            }.get(ticket.status, "❓")
            username = ticket.user_username or ticket.user_first_name or f"ID:{ticket.user_id}"
            time_ago = ModerationKeyboard._format_time_ago(ticket.created_at)
            button_text = f"{status_emoji} #{ticket.id} от {username} ({time_ago})"
            builder.row(
                CallbackButton(text=button_text, payload=f"mod_ticket_{ticket.id}")
            )

        # Кнопки пагинации
        nav_row = []
        if current_page > 1:
            nav_row.append(
                CallbackButton(
                    text="⬅️ Предыдущая",
                    payload=f"mod_tickets_page_{filter_key}_{current_page - 1}"
                )
            )
        if current_page < total_pages:
            nav_row.append(
                CallbackButton(
                    text="Следующая ➡️",
                    payload=f"mod_tickets_page_{filter_key}_{current_page + 1}"
                )
            )
        if nav_row:
            builder.row(*nav_row)

        # Кнопка возврата в главное меню модератора
        builder.row(
            CallbackButton(text="🏠 Главное меню", payload="mod_main")
        )

        return builder.as_markup()

    @staticmethod
    def ticket_details(ticket_id: int, status: str, back_filter: str = 'all'):
        """
        Детальный просмотр тикета.

        Кнопки зависят от статуса:
        - если тикет не закрыт: «📩 Ответить» и «🔒 Закрыть тикет».
        - всегда: «⬅️ Назад к списку» с учётом текущего фильтра.

        Args:
            ticket_id (int): ID тикета.
            status (str): статус тикета.
            back_filter (str): фильтр, по которому был открыт список (для возврата).

        Returns:
            InlineKeyboardMarkup: клавиатура.
        """
        builder = InlineKeyboardBuilder()

        if status != 'closed':
            builder.row(
                CallbackButton(text="📩 Ответить", payload=f"mod_reply_{ticket_id}")
            )
            builder.row(
                CallbackButton(text="🔒 Закрыть тикет", payload=f"mod_close_{ticket_id}")
            )

        builder.row(
            CallbackButton(
                text="⬅️ Назад к списку",
                payload=f"mod_tickets_{back_filter}"
            )
        )

        return builder.as_markup()

    @staticmethod
    def reply_to_ticket(ticket_id: int):
        """
        Клавиатура для ответа на тикет.

        Появляется, когда модератор начал писать ответ. Содержит только кнопку «Отмена».

        Args:
            ticket_id (int): ID тикета (для возврата).

        Returns:
            InlineKeyboardMarkup: клавиатура с одной кнопкой.
        """
        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="❌ Отмена", payload=f"mod_cancel_reply_{ticket_id}")
        )
        return builder.as_markup()

    @staticmethod
    def after_reply(ticket_id: int):
        """
        Клавиатура после отправки ответа.

        Предлагает модератору:
        - «➕ Новый ответ» – снова ответить на этот же тикет.
        - «📋 Все тикеты» – вернуться к общему списку.

        Args:
            ticket_id (int): ID тикета.

        Returns:
            InlineKeyboardMarkup: клавиатура.
        """
        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="➕ Новый ответ", payload=f"mod_reply_{ticket_id}")
        )
        builder.row(
            CallbackButton(text="📋 Все тикеты", payload="mod_tickets")
        )
        return builder.as_markup()

    @staticmethod
    def back_to_main():
        """
        Кнопка возврата в главное меню модератора.

        Используется в сообщениях, где нет других действий.

        Returns:
            InlineKeyboardMarkup: клавиатура с одной кнопкой.
        """
        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="🏠 Главное меню", payload="mod_main")
        )
        return builder.as_markup()

    @staticmethod
    def _format_time_ago(created_at):
        """
        Вспомогательный метод для форматирования времени создания тикета.

        Возвращает строку вида "5мин", "2ч" или "3д" в зависимости от того,
        сколько времени прошло с момента создания.

        Args:
            created_at (datetime): время создания тикета (с временной зоной).

        Returns:
            str: сокращённое представление времени.
        """
        now = datetime.now(timezone.utc)
        diff = now - created_at  # created_at уже имеет тип datetime (с зоной)
        seconds = diff.total_seconds()

        if seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}мин"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}ч"
        else:
            days = int(seconds / 86400)
            return f"{days}д"
