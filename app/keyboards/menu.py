"""
Клавиатуры для главного меню и подменю.
"""

from maxbot.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton(text="💰 Мой баланс", callback_data="balance")],
        [InlineKeyboardButton(text="🪪 Виртуальная карта", callback_data="virtual_card")],
        [InlineKeyboardButton(text="🆘 Отдел заботы", callback_data="support")],
        [InlineKeyboardButton(text="💼 Вакансии", callback_data="vacancies")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_support_submenu_keyboard(has_tickets: bool = False) -> InlineKeyboardMarkup:
    """Подменю отдела заботы"""
    keyboard = [
        [InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data="support_feedback")],
        [InlineKeyboardButton(text="❓ Мне только спросить", callback_data="support_question")],
    ]
    if has_tickets:
        keyboard.append([InlineKeyboardButton(text="📋 Мои обращения", callback_data="my_tickets")])
    keyboard.append([InlineKeyboardButton(text="📧 Контакты", callback_data="support_contacts")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    keyboard = [[
        InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")
    ]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_to_support_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в отдел заботы"""
    keyboard = [[
        InlineKeyboardButton(text="🔙 Назад в отдел заботы", callback_data="back_to_support")
    ]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
