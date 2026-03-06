from maxbot.types import InlineKeyboardMarkup, InlineKeyboardButton


def retry_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для повторной попытки регистрации в iiko.
    """
    keyboard = [[
        InlineKeyboardButton(text="🔄 Повторить попытку", callback_data="retry_iiko_registration")
    ]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
