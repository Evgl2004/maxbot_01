"""
Middleware для автоматического сохранения пользователей в базу данных.

При каждом событии, содержащем информацию об отправителе, сохраняет или обновляет
запись о пользователе в таблице users. Используется для актуальности данных.
"""

from loguru import logger
from maxapi.filters.middleware import BaseMiddleware
from app.database import db


class UserSaveMiddleware(BaseMiddleware):
    """
    Промежуточный обработчик для сохранения пользователя.
    """

    async def __call__(self, handler, event, data):
        """
        Вызывается для каждого события.

        Args:
            handler: следующий обработчик
            event: объект события
            data: словарь с дополнительными данными

        Returns:
            Результат вызова следующего обработчика.
        """
        user = getattr(event, 'from_user', None)
        if user and not getattr(user, 'is_bot', False):
            user_id = getattr(user, 'user_id', None)
            first_name = getattr(user, 'first_name', '')
            last_name = getattr(user, 'last_name', '')
            # В maxapi username обычно хранится в поле 'name'
            username = getattr(user, 'name', '')
            if not username:
                # Если name отсутствует, формируем из first_name и last_name
                username = f"{first_name} {last_name}".strip()
                if not username:
                    username = f"user_{user_id}"
            try:
                if user_id:
                    await db.add_user(
                        user_id=user_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name
                    )
            except Exception as e:
                logger.error(f"❌ Ошибка при сохранении пользователя {user_id}: {e}")
        return await handler(event, data)
