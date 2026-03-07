"""
Пакет промежуточных обработчиков (middleware)
================================================
Функция setup_middlewares подключает все необходимые middleware к диспетчеру.
Порядок подключения важен: сначала логирование, потом сохранение пользователя.
"""

from maxapi.dispatcher import Dispatcher
from .logging import LoggingMiddleware
from .user import UserSaveMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    """
    Добавляет список middleware в диспетчер.

    Args:
        dp (Dispatcher): экземпляр диспетчера, в который добавляются middleware.
    """
    dp.middlewares = [
        LoggingMiddleware(),   # логирует все события
        UserSaveMiddleware(),  # сохраняет пользователя в БД
    ]
