"""
Пакет обработчиков (handlers) приложения.
===========================================
Этот файл объединяет все роутеры бота и предоставляет функцию setup_routers
для их регистрации в диспетчере.
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
    Регистрация всех роутеров в диспетчере.

    Аргументы:
        dp (Dispatcher): диспетчер бота, в который добавляются роутеры.
    """
    # Метод include_routers принимает несколько аргументов и добавляет их в список роутеров диспетчера
    dp.include_routers(
        start_router,   # обрабатывает /start
        help_router,            # обрабатывает /help и /status
        registration_router,    # все шаги регистрации (FSM)
        menu_router,            # навигация по главному меню
        legacy_router,          # обновление legacy-пользователей
        admin_router,           # админские команды и рассылки
        moderation_router,      # модерация тикетов
        user_tickets_router     # просмотр и ответы на тикеты
    )
