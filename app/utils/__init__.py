"""
Пакет утилит
=============
Содержит вспомогательные функции для валидации, работы с профилем,
генерации QR-кодов и форматирования тикетов.
"""

from .validation import (
    validate_first_name,
    validate_last_name,
    validate_birth_date,
    validate_email,
    clean_name,
    confirm_text,
)
from .profile import show_profile_review
from .qr import generate_qr_code
from .ticket_formatter import format_ticket_details, localize_status

__all__ = [
    # validation
    'validate_first_name',
    'validate_last_name',
    'validate_birth_date',
    'validate_email',
    'clean_name',
    'confirm_text',
    # profile
    'show_profile_review',
    # qr
    'generate_qr_code',
    # ticket_formatter
    'format_ticket_details',
    'localize_status',
]
