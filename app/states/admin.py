"""
Состояния для админской части
"""

from maxbot.fsm import State, StatesGroup


class AdminStates(StatesGroup):
    """Состояния для админских функций"""
    
    # Состояния для рассылки
    broadcast_message = State()  # Ожидание сообщения для рассылки
    broadcast_button = State()   # Ожидание кнопки для рассылки
    broadcast_confirm = State()  # Подтверждение рассылки
