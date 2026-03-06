"""
Middleware для логирования входящих событий
=============================================
Логирование сообщения и нажатия на кнопки.
"""

from loguru import logger
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types import MessageCreated, MessageCallback


class LoggingMiddleware(BaseMiddleware):
    """
    📝 Промежуточный обработчик для логирования.

    Для каждого входящего события проверяет его тип и записывает в лог
    информацию об отправителе и содержании.
    """

    async def __call__(self, handler, event, data):
        """
        Основной метод, вызываемый при каждом событии.

        Аргументы:
            handler: следующий обработчик (функция или другой middleware)
            event: объект события (например, MessageCreated, MessageCallback)
            data: словарь с дополнительными данными (контекст и т.п.)
        """
        # Если событие — новое сообщение
        if isinstance(event, MessageCreated):
            user = event.from_user
            # Безопасно получаем текст сообщения (может быть None)
            text = event.message.body.text[:50] if event.message.body.text else 'нет текста'
            logger.info(f"📥 Сообщение от {user.id} ({user.name}): '{text}'")

        # Если событие — нажатие на callback-кнопку
        elif isinstance(event, MessageCallback):
            user = event.from_user
            payload = event.callback.payload
            logger.info(f"🔘 Callback от {user.id} ({user.name}): '{payload}'")

        # Передаём управление дальше по цепочке
        return await handler(event, data)
