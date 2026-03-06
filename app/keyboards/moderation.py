"""
Клавиатуры для системы модерации
"""

from typing import List
from maxbot.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.database.models import Ticket


class ModerationKeyboard:
    """Клавиатуры для системы модерации"""

    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Главное меню модератора"""
        buttons = [
            [InlineKeyboardButton(text="📋 Все тикеты", callback_data="mod_tickets_all")],
            [InlineKeyboardButton(text="🆕 Новые тикеты", callback_data="mod_tickets_open")],
            [InlineKeyboardButton(text="🔄 В работе", callback_data="mod_tickets_progress")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def tickets_list(
            tickets: List[Ticket],
            current_page: int = 1,
            total_pages: int = 1,
            filter_key: str = 'all'
    ) -> InlineKeyboardMarkup:
        """Список тикетов с пагинацией"""
        keyboard = []

        # Кнопки тикетов
        for ticket in tickets:
            status_emoji = {
                "open": "🆕",
                "in_progress": "🔄",
                "closed": "🔒"
            }.get(ticket.status, "❓")
            username = ticket.user_username or ticket.user_first_name or f"ID:{ticket.user_id}"
            time_ago = ModerationKeyboard._format_time_ago(ticket.created_at)
            button_text = f"{status_emoji} #{ticket.id} от {username} ({time_ago})"
            keyboard.append([
                InlineKeyboardButton(text=button_text, callback_data=f"mod_ticket_{ticket.id}")
            ])

        # Кнопки навигации
        nav_row = []
        if current_page > 1:
            nav_row.append(InlineKeyboardButton(
                text="⬅️ Предыдущая",
                callback_data=f"mod_tickets_page_{filter_key}_{current_page - 1}"
            ))
        if current_page < total_pages:
            nav_row.append(InlineKeyboardButton(
                text="Следующая ➡️",
                callback_data=f"mod_tickets_page_{filter_key}_{current_page + 1}"
            ))
        if nav_row:
            keyboard.append(nav_row)

        # Кнопка возврата
        keyboard.append([
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="mod_main")
        ])

        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def ticket_details(ticket_id: int, status: str, back_filter: str = 'all') -> InlineKeyboardMarkup:
        """Детальный просмотр тикета"""
        keyboard = []
        if status != 'closed':
            keyboard.append([
                InlineKeyboardButton(text="📩 Ответить", callback_data=f"mod_reply_{ticket_id}")
            ])
            keyboard.append([
                InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"mod_close_{ticket_id}")
            ])
        keyboard.append([
            InlineKeyboardButton(text="⬅️ Назад к списку", callback_data=f"mod_tickets_{back_filter}")
        ])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def reply_to_ticket(ticket_id: int) -> InlineKeyboardMarkup:
        """Клавиатура для ответа на тикет"""
        keyboard = [[
            InlineKeyboardButton(text="Отмена", callback_data=f"mod_ticket_{ticket_id}")
        ]]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def after_reply(ticket_id: int) -> InlineKeyboardMarkup:
        """Клавиатура после отправки ответа"""
        keyboard = [
            [InlineKeyboardButton(text="➕ Новый ответ", callback_data=f"mod_reply_{ticket_id}")],
            [InlineKeyboardButton(text="📋 Все тикеты", callback_data="mod_tickets")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def back_to_main() -> InlineKeyboardMarkup:
        """Кнопка возврата в главное меню"""
        keyboard = [[
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="mod_main")
        ]]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def _format_time_ago(created_at) -> str:
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = now - created_at
        if diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes}мин"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}ч"
        else:
            days = int(diff.total_seconds() / 86400)
            return f"{days}д"
