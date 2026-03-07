"""
Middleware для логирования входящих событий.
Логирует сообщения и нажатия на callback-кнопки.

Данный middleware перехватывает все события до обработчиков и записывает
в лог информацию о каждом сообщении или callback'е.
"""

from loguru import logger
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types import MessageCreated, MessageCallback


class LoggingMiddleware(BaseMiddleware):
    """
    Промежуточный обработчик, который логирует информацию о каждом входящем событии.
    """

    async def __call__(self, handler, event, data):
        """
        Вызывается для каждого события.

        Args:
            handler: следующий обработчик в цепочке
            event: объект события (MessageCreated или MessageCallback)
            data: словарь с дополнительными данными (может содержать контекст и т.п.)

        Returns:
            Результат вызова следующего обработчика.
        """
        if isinstance(event, MessageCreated):
            user = event.from_user
            user_id = getattr(user, 'user_id', None)
            if user_id:
                user_name = getattr(user, 'name', 'Неизвестно')
                text = event.message.body.text[:50] if event.message.body.text else 'нет текста'
                logger.info(f"📥 Сообщение от {user_id} ({user_name}): '{text}'")
        elif isinstance(event, MessageCallback):
            user = event.from_user
            user_id = getattr(user, 'user_id', None)
            if user_id:
                user_name = getattr(user, 'name', 'Неизвестно')
                payload = event.callback.payload
                logger.info(f"🔘 Callback от {user_id} ({user_name}): '{payload}'")
        return await handler(event, data)
