"""
Состояния для админской части
================================
Используются в процессе создания рассылки: ожидание сообщения, кнопки, подтверждение.
"""

from maxapi.context import State, StatesGroup


class AdminStates(StatesGroup):
    """
    Группа состояний для админских функций.

    Атрибуты:
        broadcast_message: ожидание сообщения для рассылки
        broadcast_button: ожидание кнопки для рассылки
        broadcast_confirm: подтверждение рассылки
    """
    broadcast_message = State()  # пользователь должен отправить сообщение
    broadcast_button = State()   # пользователь должен отправить кнопку (текст|url)
    broadcast_confirm = State()  # подтверждение перед отправкой
