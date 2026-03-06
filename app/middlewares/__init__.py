"""
Пакет промежуточных обработчиков (middleware)
===============================================
Здесь собираются все middleware, которые будут подключены к диспетчеру.
Функция setup_middlewares добавляет их в глобальный список диспетчера.
"""

from maxapi.dispatcher import Dispatcher

# Импортируем сами классы middleware
from .logging import LoggingMiddleware
from .user import UserSaveMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    """
    🛠️ Подключает все необходимые middleware к диспетчеру.

    Аргументы:
        dp (Dispatcher): экземпляр диспетчера, в который добавляются middleware.
    """
    # Список middleware, которые будут выполняться последовательно
    dp.middlewares = [
        LoggingMiddleware(),   # логирование всех событий
        UserSaveMiddleware(),  # автоматическое сохранение пользователя
    ]
