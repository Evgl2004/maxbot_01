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
      - username: отображаемое имя (user.name)
      - first_name: имя пользователя
      - last_name: фамилия

    Ошибки при сохранении логируются, но не прерывают обработку события,
    чтобы пользователь всё равно получил ответ от бота.
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
        # Пытаемся получить объект пользователя из события
        # У многих типов событий есть атрибут from_user.
        user = getattr(event, 'from_user', None)

        # Если пользователь существует и не является ботом (is_bot == False)
        if user and not getattr(user, 'is_bot', False):
            # В maxapi у объекта User нет поля id, используется user_id.
            # Получаем user_id заранее, чтобы использовать в логах даже при ошибке.
            user_id = getattr(user, 'user_id', None)

            try:
                if user_id:
                    # Сохраняем пользователя в БД (метод add_user сам решает, создать или обновить)
                    await db.add_user(
                        user_id=user_id,
                        username=user.name,          # в MAX это отображаемое имя (обычно содержит логин)
                        first_name=user.first_name,
                        last_name=user.last_name
                    )
            except Exception as e:
                # Логируем ошибку, но не прерываем обработку события.
                # Переменная user_id уже определена, поэтому предупреждения PyCharm не будет.
                logger.error(f"❌ Ошибка при сохранении пользователя {user_id}: {e}")

        # Передаём управление дальше по цепочке
        return await handler(event, data)
