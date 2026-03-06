"""
Пакет сервисов приложения
===========================
Предоставляет сервисы для работы с iiko, тикетами, рассылками и синхронизацией пользователей.
"""

from .broadcast import BroadcastService
from . import iiko_service
from .tickets import ticket_service
from .user_sync import sync_user_with_iiko

__all__ = [
    'BroadcastService',
    'iiko_service',
    'ticket_service',
    'sync_user_with_iiko',
]
