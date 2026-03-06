"""
Утилиты для логирования
"""
from functools import wraps
from loguru import logger
from maxbot.types import Message, Callback


def log_event(event):
    """Логирует входящее событие maxbot"""
    if isinstance(event, Message):
        user = event.sender
        text = event.text[:50] if event.text else 'No text'
        logger.info(f"📥 Message from {user.id} (@{user.username}): '{text}'")
    elif isinstance(event, Callback):
        user = event.user
        logger.info(f"🔘 Callback from {user.id} (@{user.username}): '{event.payload}'")
    # Можно добавить обработку bot_started, если нужно


def with_logging(handler):
    @wraps(handler)
    async def wrapper(event, *args, **kwargs):
        log_event(event)
        try:
            return await handler(event, *args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Error in handler: {e}")
            raise
    return wrapper
