from typing import List
from maxbot.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.database.models import Ticket


class UserTicketsKeyboard:
    """Клавиатуры для раздела «Мои обращения»"""

    @staticmethod
    def tickets_list(tickets: List[Ticket], current_page: int, total_pages: int) -> InlineKeyboardMarkup:
        """Список тикетов с пагинацией"""
        keyboard = []

        for ticket in tickets:
            status_emoji = {
                "open": "🆕",
                "in_progress": "🔄",
                "closed": "🔒"
            }.get(ticket.status, "❓")
            short_question = (ticket.message[:20] + "…") if len(ticket.message) > 20 else ticket.message
            button_text = f"{status_emoji} #{ticket.id} от {ticket.created_at.strftime('%d.%m')}: {short_question}"
            keyboard.append([
                InlineKeyboardButton(text=button_text, callback_data=f"user_ticket_{ticket.id}")
            ])

        # Пагинация
        nav_row = []
        if current_page > 1:
            nav_row.append(InlineKeyboardButton(
                text="⬅️ Предыдущая",
                callback_data=f"user_tickets_page_{current_page - 1}"
            ))
        if current_page < total_pages:
            nav_row.append(InlineKeyboardButton(
                text="Следующая ➡️",
                callback_data=f"user_tickets_page_{current_page + 1}"
            ))
        if nav_row:
            keyboard.append(nav_row)

        # Назад в отдел заботы
        keyboard.append([
            InlineKeyboardButton(text="🔙 Назад в отдел заботы", callback_data="back_to_support")
        ])

        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def back_to_support() -> InlineKeyboardMarkup:
        """Кнопка назад в отдел заботы"""
        keyboard = [[
            InlineKeyboardButton(text="🔙 Назад в отдел заботы", callback_data="back_to_support")
        ]]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def ticket_details(ticket_id: int, status: str) -> InlineKeyboardMarkup:
        """Детали тикета для пользователя"""
        keyboard = []
        if status != 'closed':
            keyboard.append([
                InlineKeyboardButton(text="📝 Ответить", callback_data=f"user_reply_{ticket_id}")
            ])
        keyboard.append([
            InlineKeyboardButton(text="🔙 Назад к списку", callback_data="my_tickets")
        ])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def cancel_reply(ticket_id: int) -> InlineKeyboardMarkup:
        """Отмена ответа на тикет"""
        keyboard = [[
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"user_ticket_{ticket_id}")
        ]]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def notification_keyboard(ticket_id: int, status: str) -> InlineKeyboardMarkup:
        """Уведомление о новом ответе модератора"""
        keyboard = []
        if status != 'closed':
            keyboard.append([
                InlineKeyboardButton(text="📝 Ответить", callback_data=f"user_reply_{ticket_id}")
            ])
        keyboard.append([
            InlineKeyboardButton(text="📋 Мои обращения", callback_data="my_tickets")
        ])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
