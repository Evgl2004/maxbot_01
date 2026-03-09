"""
Клиент Redis для хранения состояния между запусками.

Используется для сохранения маркера обновлений (marker_updates) бота,
чтобы после перезапуска продолжить получение событий с того же места,
избегая повторной обработки старых сообщений.
"""

import redis.asyncio as redis
from loguru import logger
from app.config import settings
from typing import Optional

_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """
    Возвращает асинхронный клиент Redis (создаёт при первом вызове).
    Клиент настроен на автоматическую декодировку ответов (decode_responses=True).
    """
    global _redis_client
    if _redis_client is None:
        logger.info("🔄 Подключение к Redis...")
        _redis_client = await redis.from_url(
            settings.redis_url,
            decode_responses=True
        )
        logger.info("✅ Подключение к Redis установлено")
    return _redis_client


async def close_redis() -> None:
    """Закрывает соединение с Redis."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("🔒 Соединение с Redis закрыто")
