"""
Декоратор для автоматического сохранения пользователя в БД
"""
from functools import wraps
from loguru import logger
from maxbot.types import Message, Callback
from app.database import db


def extract_user(event):
    """Извлекает объект User из события maxbot"""
    if isinstance(event, Message):
        return event.sender
    elif isinstance(event, Callback):
        return event.user
    # При необходимости можно добавить обработку bot_started
    return None


def with_user_save(handler):
    @wraps(handler)
    async def wrapper(event, *args, **kwargs):
        user = extract_user(event)
        if user and not getattr(user, 'is_bot', False):
            try:
                await db.add_user(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
            except Exception as e:
                logger.error(f"Ошибка при сохранении пользователя {user.id}: {e}")
        return await handler(event, *args, **kwargs)
    return wrapper
