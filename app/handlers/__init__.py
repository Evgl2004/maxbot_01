"""
Пакет обработчиков (handlers) приложения.
===========================================
Этот файл объединяет все роутеры бота и предоставляет функцию setup_routers
для их регистрации в диспетчере. Порядок регистрации важен: роутеры обрабатываются
в том порядке, в котором они переданы в метод include_routers. Если один и тот же
тип события может быть обработан несколькими роутерами, сработает первый подходящий.

В данном проекте порядок выбран следующим образом:
- start_router – обрабатывает команду /start, перенаправляя в регистрацию или меню.
- help_router – команды /help и /status.
- registration_router – все шаги регистрации (FSM).
- menu_router – главное меню и навигация.
- legacy_router – обновление устаревших пользователей (FSM).
- admin_router – админские команды и рассылки (FSM).
- moderation_router – модерация тикетов (FSM).
- user_tickets_router – раздел «Мои обращения» (FSM).
"""

from maxapi.dispatcher import Dispatcher

# Импортируем роутеры из всех модулей
from .start import router as start_router
from .help import router as help_router
from .registration import router as registration_router
from .menu import router as menu_router
from .legacy import router as legacy_router
from .admin import combined_router as admin_router
from .moderation import router as moderation_router
from .user_tickets import router as user_tickets_router


def setup_routers(dp: Dispatcher) -> None:
    """
    Регистрирует все роутеры в диспетчере.

    Args:
        dp (Dispatcher): экземпляр диспетчера, в который будут добавлены роутеры.
    """
    # Метод include_routers принимает произвольное количество аргументов
    # и добавляет их в список роутеров диспетчера в порядке перечисления.
    dp.include_routers(
        start_router,           # обрабатывает /start
        help_router,            # обрабатывает /help и /status
        registration_router,    # все шаги регистрации (FSM)
        menu_router,            # навигация по главному меню
        legacy_router,          # обновление legacy-пользователей
        admin_router,           # админские команды и рассылки
        moderation_router,      # модерация тикетов
        user_tickets_router     # просмотр и ответы на тикеты
    )
