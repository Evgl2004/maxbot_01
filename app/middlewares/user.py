"""
Middleware для автоматического сохранения пользователей в базу данных
========================================================================
При каждом событии, в котором есть отправитель, сохраняет или обновляет запись о пользователе.
"""

from loguru import logger
from maxapi.filters.middleware import BaseMiddleware
from app.database import db


class UserSaveMiddleware(BaseMiddleware):
    """
    👤 Промежуточный обработчик для сохранения пользователя.

    Извлекает из события объект пользователя (from_user) и передаёт его
    в метод db.add_user() для записи в базу данных.
    """

    async def __call__(self, handler, event, data):
        """
        Основной метод, вызываемый при каждом событии.

        Аргументы:
            handler: следующий обработчик
            event: объект события
            data: словарь с дополнительными данными
        """
        # Пытаемся получить пользователя из события
        user = getattr(event, 'from_user', None)

        # Если пользователь есть и он не бот
        if user and not getattr(user, 'is_bot', False):
            try:
                # Сохраняем в базу (метод add_user сам решает, создать или обновить)
                await db.add_user(
                    user_id=user.id,
                    username=user.name,          # в MAX это отображаемое имя (обычно содержит username)
                    first_name=user.first_name,
                    last_name=user.last_name
                )
            except Exception as e:
                logger.error(f"❌ Ошибка при сохранении пользователя {user.id}: {e}")

        # Передаём управление дальше
        return await handler(event, data)
