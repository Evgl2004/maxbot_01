"""
Контекст пользователя с хранением данных в Redis.
Используется для сохранения состояний FSM между перезапусками бота.
"""

import json
from typing import Any, Optional, Union

from maxapi.context import MemoryContext, State
from app.services.redis_client import get_redis

from loguru import logger

# Глобальный реестр состояний: имя_состояния -> объект State
_STATE_REGISTRY = {}


def build_state_registry():
    """
    Строит реестр всех состояний, определённых в проекте.
    Вызывается один раз при старте бота.
    """
    global _STATE_REGISTRY
    # Импортируем все группы состояний
    from app.states import registration, legacy, admin, tickets
    groups = [
        registration.Registration,
        legacy.LegacyUpgrade,
        admin.AdminStates,
        tickets.TicketStates,
        tickets.UserTicketStates,
    ]
    for group in groups:
        for attr_name in dir(group):
            attr = getattr(group, attr_name)
            if isinstance(attr, State):
                _STATE_REGISTRY[str(attr)] = attr
                logger.debug(f"Зарегистрировано состояние: {str(attr)}")
    logger.info(f"Реестр состояний содержит {len(_STATE_REGISTRY)} записей: {list(_STATE_REGISTRY.keys())}")


class RedisContext(MemoryContext):
    """
    Контекст, хранящий данные и состояние в Redis.
    Полностью повторяет интерфейс MemoryContext, но данные сохраняются в Redis.
    """

    def __init__(self, chat_id: int, user_id: int):
        super().__init__(chat_id, user_id)
        self._redis = None  # lazy initialization

    async def _get_redis(self):
        """Возвращает клиент Redis (создаёт при первом обращении)."""
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis

    def _make_data_key(self) -> str:
        """Ключ для хранения данных пользователя."""
        return f"fsm:{self.chat_id}:{self.user_id}:data"

    def _make_state_key(self) -> str:
        """Ключ для хранения состояния пользователя."""
        return f"fsm:{self.chat_id}:{self.user_id}:state"

    async def get_data(self) -> dict[str, Any]:
        """Возвращает данные из Redis."""
        redis = await self._get_redis()
        data_json = await redis.get(self._make_data_key())
        if data_json:
            return json.loads(data_json)
        return {}

    async def set_data(self, data: dict[str, Any]):
        """Сохраняет данные в Redis."""
        redis = await self._get_redis()
        await redis.set(self._make_data_key(), json.dumps(data))

    async def update_data(self, **kwargs):
        """Обновляет данные в Redis."""
        data = await self.get_data()
        data.update(kwargs)
        await self.set_data(data)

    async def get_state(self) -> Optional[State]:
        """
        Возвращает текущее состояние из Redis.
        Использует глобальный реестр для преобразования строки в объект State.
        """
        redis = await self._get_redis()
        state_str = await redis.get(self._make_state_key())
        logger.debug(f"Запрошено состояние для {self.chat_id}:{self.user_id}, из Redis получено: {state_str}")
        if state_str:
            # Получаем объект State из реестра
            state_obj = _STATE_REGISTRY.get(state_str)
            logger.debug(f"По строке '{state_str}' найден объект State: {state_obj}")
            return state_obj
        logger.debug(f"Состояние не найдено в Redis или не зарегистрировано")
        return None

    async def set_state(self, state: Optional[Union[State, str]] = None):
        """Устанавливает состояние в Redis (сохраняет строковое представление)."""
        redis = await self._get_redis()
        if state is None:
            await redis.delete(self._make_state_key())
            logger.debug(f"Удалено состояние для {self.chat_id}:{self.user_id}")
        else:
            state_val = str(state)
            await redis.set(self._make_state_key(), state_val)
            logger.debug(f"Сохранено состояние для {self.chat_id}:{self.user_id} -> {state_val}")

    async def clear(self):
        """Очищает данные и состояние в Redis."""
        redis = await self._get_redis()
        await redis.delete(self._make_data_key(), self._make_state_key())
