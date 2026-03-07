"""
Admin handlers package
=======================
Экспортирует комбинированный роутер из модуля admin.py для подключения
в общем файле handlers/__init__.py.
"""

from .admin import router as combined_router

__all__ = ["combined_router"]
