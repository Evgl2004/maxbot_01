"""
Пакет обработчиков административной части
===========================================
Объединяет роутеры админки и предоставляет единый роутер для подключения.
"""

from maxapi import Router

from .admin import router as admin_router
# from .api_settings import router as api_settings_router  # временно отключено (Local API не актуален)

# Создаём комбинированный роутер для административных функций
combined_router = Router()
combined_router.include_router(admin_router)
# combined_router.include_router(api_settings_router)  # закомментировано

# Экспортируем комбинированный роутер для подключения в handlers/__init__.py
__all__ = ["combined_router"]
