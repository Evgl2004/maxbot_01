"""
Клавиатуры для сервиса iiko
=============================
Содержит функции для создания клавиатур, связанных с интеграцией iiko.
В данный момент только кнопка для повторной попытки регистрации.
"""

from maxapi.types import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


def retry_keyboard():
    """
    🔄 Клавиатура для повторной попытки регистрации в iiko.

    Используется при временных сбоях сети или ошибках API iiko.
    Пользователь может нажать кнопку, чтобы повторить попытку синхронизации.

    Возвращает:
        InlineKeyboardMarkup (attachment): клавиатура с одной кнопкой.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(
            text="🔄 Повторить попытку",
            payload="retry_iiko_registration"
        )
    )
    return builder.as_markup()
