"""
Клавиатуры для раздела «Мои обращения»
========================================
Содержат функции для создания клавиатур:
- списка тикетов пользователя с пагинацией
- просмотра деталей тикета
- ответа на тикет
- уведомлений о новых ответах
"""

from typing import List

from maxapi.types import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from app.database.models import Ticket  # для аннотации типа


class UserTicketsKeyboard:
    """
    👤 Клавиатуры для пользовательского раздела «Мои обращения».

    Все методы возвращают готовую inline-клавиатуру (объект вложения),
    которую нужно передавать в параметре attachments при отправке сообщения.
    """

    @staticmethod
    def tickets_list(tickets: List[Ticket], current_page: int, total_pages: int):
        """
        📋 Список тикетов пользователя с пагинацией.

        Для каждого тикета создаётся кнопка с эмодзи статуса, номером, датой и
        первыми 20 символами вопроса. Кнопка ведёт к просмотру деталей тикета.

        Аргументы:
            tickets (List[Ticket]): список тикетов для текущей страницы
            current_page (int): номер текущей страницы
            total_pages (int): общее количество страниц

        Возвращает:
            InlineKeyboardMarkup (attachment): клавиатура с кнопками тикетов,
            кнопками навигации и кнопкой возврата в отдел заботы.
        """
        builder = InlineKeyboardBuilder()

        # Кнопки для каждого тикета
        for ticket in tickets:
            # Выбираем эмодзи в зависимости от статуса
            status_emoji = {
                "open": "🆕",
                "in_progress": "🔄",
                "closed": "🔒"
            }.get(ticket.status, "❓")

            # Обрезаем длинный вопрос
            short_question = (ticket.message[:20] + "…") if len(ticket.message) > 20 else ticket.message
            # Формируем текст кнопки: статус, номер, дата, вопрос
            button_text = f"{status_emoji} #{ticket.id} от {ticket.created_at.strftime('%d.%m')}: {short_question}"
            # Кнопка ведёт к деталям тикета
            builder.row(
                CallbackButton(text=button_text, payload=f"user_ticket_{ticket.id}")
            )

        # Кнопки пагинации (Предыдущая / Следующая)
        nav_row = []
        if current_page > 1:
            nav_row.append(
                CallbackButton(
                    text="⬅️ Предыдущая",
                    payload=f"user_tickets_page_{current_page - 1}"
                )
            )
        if current_page < total_pages:
            nav_row.append(
                CallbackButton(
                    text="Следующая ➡️",
                    payload=f"user_tickets_page_{current_page + 1}"
                )
            )
        if nav_row:
            builder.row(*nav_row)

        # Кнопка возврата в отдел заботы
        builder.row(
            CallbackButton(text="🔙 Назад в отдел заботы", payload="back_to_support")
        )

        return builder.as_markup()

    @staticmethod
    def back_to_support():
        """
        🔙 Простая кнопка возврата в отдел заботы.

        Используется в сообщениях, где нет других действий.
        """
        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="🔙 Назад в отдел заботы", payload="back_to_support")
        )
        return builder.as_markup()

    @staticmethod
    def ticket_details(ticket_id: int, status: str):
        """
        🎫 Детали тикета для пользователя.

        Кнопки:
        - «📝 Ответить» – если тикет не закрыт (позволяет ответить).
        - «🔙 Назад к списку» – возврат к списку обращений.

        Аргументы:
            ticket_id (int): ID тикета (для формирования payload).
            status (str): статус тикета ('open', 'in_progress', 'closed').

        Возвращает:
            InlineKeyboardMarkup.
        """
        builder = InlineKeyboardBuilder()

        if status != 'closed':
            builder.row(
                CallbackButton(text="📝 Ответить", payload=f"user_reply_{ticket_id}")
            )

        builder.row(
            CallbackButton(text="🔙 Назад к списку", payload="my_tickets")
        )

        return builder.as_markup()

    @staticmethod
    def cancel_reply(ticket_id: int):
        """
        ❌ Отмена ответа на тикет.

        Появляется, когда пользователь начал писать ответ, но передумал.
        Кнопка возвращает к деталям тикета.

        Аргументы:
            ticket_id (int): ID тикета.

        Возвращает:
            InlineKeyboardMarkup с одной кнопкой «❌ Отмена».
        """
        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="❌ Отмена", payload=f"user_ticket_{ticket_id}")
        )
        return builder.as_markup()

    @staticmethod
    def notification_keyboard(ticket_id: int, status: str):
        """
        🔔 Клавиатура для уведомления о новом ответе модератора.

        Отправляется пользователю, когда модератор ответил на его тикет.
        Содержит кнопку «📝 Ответить» (если тикет не закрыт) и
        кнопку «📋 Мои обращения».

        Аргументы:
            ticket_id (int): ID тикета
            status (str): текущий статус тикета

        Возвращает:
            InlineKeyboardMarkup.
        """
        builder = InlineKeyboardBuilder()

        if status != 'closed':
            builder.row(
                CallbackButton(text="📝 Ответить", payload=f"user_reply_{ticket_id}")
            )

        builder.row(
            CallbackButton(text="📋 Мои обращения", payload="my_tickets")
        )

        return builder.as_markup()
