"""
Пакет сервисов приложения
===========================
Предоставляет сервисы для работы с iiko, тикетами, рассылками и синхронизацией пользователей.
"""

from .broadcast import BroadcastService
from . import iiko_service
from .tickets import ticket_service
from .user_sync import sync_user_with_iiko
from .redis_client import get_redis, close_redis

__all__ = [
    'BroadcastService',
    'iiko_service',
    'ticket_service',
    'sync_user_with_iiko',
    'get_redis',
    'close_redis',
]
