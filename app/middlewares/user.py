"""
Middleware для автоматического сохранения пользователей в базу данных
========================================================================
Этот модуль содержит класс UserSaveMiddleware, который при каждом событии,
содержащем информацию о пользователе, сохраняет или обновляет запись
о пользователе в таблице users базы данных.
"""

from loguru import logger
from maxapi.filters.middleware import BaseMiddleware
from app.database import db


class UserSaveMiddleware(BaseMiddleware):
    """
    👤 Класс промежуточного обработчика для сохранения пользователя.

    Наследуется от BaseMiddleware. При каждом событии пытается извлечь объект
    пользователя (from_user). Если пользователь существует и не является ботом,
    сохраняет его в базу данных через db.add_user().

    Поля, сохраняемые в БД:
      - user_id: идентификатор пользователя (в maxapi это поле user_id, а не id)
      - username: отображаемое имя (пытаемся взять из user.name, если нет – склеиваем first_name и last_name)
      - first_name: имя пользователя
      - last_name: фамилия

    Ошибки при сохранении логируются, но не прерывают обработку события.
    """

    async def __call__(self, handler, event, data):
        """
        Основной метод, вызываемый для каждого события.

        Аргументы:
            handler: следующий обработчик в цепочке
            event: объект события (MessageCreated, MessageCallback и др.)
            data: словарь с дополнительными данными (контекст FSM и т.п.)

        Возвращает:
            Результат вызова следующего обработчика.
        """
        user = getattr(event, 'from_user', None)

        if user and not getattr(user, 'is_bot', False):
            # Получаем user_id (обязательно есть)
            user_id = getattr(user, 'user_id', None)

            # Безопасно получаем first_name и last_name
            first_name = getattr(user, 'first_name', '')
            last_name = getattr(user, 'last_name', '')

            # Пытаемся получить name, если есть; иначе составляем из first_name и last_name
            username = getattr(user, 'name', '')
            if not username:
                username = f"{first_name} {last_name}".strip()
                if not username:
                    username = f"user_{user_id}"  # запасной вариант

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
