"""
Клавиатуры для админской части
"""

from maxbot.types import InlineKeyboardMarkup, InlineKeyboardButton


class AdminKeyboards:
    """Клавиатуры для админской панели"""

    @staticmethod
    def main_admin_menu() -> InlineKeyboardMarkup:
        """Главное меню админа"""
        keyboard = [
            [InlineKeyboardButton(text="📊 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="👨‍💼 Модератор", callback_data="mod_main")],
            [InlineKeyboardButton(text="⚙️ Настройки API", callback_data="admin_api_settings")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def broadcast_confirm(message_count: int) -> InlineKeyboardMarkup:
        """Подтверждение рассылки"""
        keyboard = [
            [InlineKeyboardButton(text=f"✅ Отправить ({message_count} польз.)",
                                   callback_data="broadcast_confirm_yes")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_confirm_no")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def broadcast_add_button() -> InlineKeyboardMarkup:
        """Меню добавления кнопки к рассылке"""
        keyboard = [
            [InlineKeyboardButton(text="➕ Добавить кнопку", callback_data="broadcast_add_button")],
            [InlineKeyboardButton(text="📤 Отправить без кнопки", callback_data="broadcast_no_button")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_cancel")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def broadcast_button_confirm() -> InlineKeyboardMarkup:
        """Подтверждение кнопки для рассылки"""
        keyboard = [
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="broadcast_button_confirm")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_cancel")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def create_custom_button(text: str, url: str) -> InlineKeyboardMarkup:
        """Создание кастомной кнопки для рассылки"""
        keyboard = [[
            InlineKeyboardButton(text=text, url=url)
        ]]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def api_settings_menu(is_local_mode: bool) -> InlineKeyboardMarkup:
        """Меню настроек API (оставлено для совместимости, но в MAX не актуально)"""
        switch_text = "🌍 Перейти на Public API" if is_local_mode else "🟢 Перейти на Local API"
        keyboard = [
            [InlineKeyboardButton(text=switch_text, callback_data="api_switch_mode")],
            [InlineKeyboardButton(text="📊 Проверить статус", callback_data="api_check_status")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="api_back")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def api_settings_back() -> InlineKeyboardMarkup:
        """Кнопка возврата из инструкций"""
        keyboard = [[
            InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data="admin_api_settings")
        ]]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
