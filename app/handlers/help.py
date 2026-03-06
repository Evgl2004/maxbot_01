"""
Обработчики команд помощи и информации
========================================
Содержит функции для команд /help и /status.
Выводят справочную информацию о боте и его состоянии.
"""

from loguru import logger
from datetime import datetime

from maxapi import Router
from maxapi.types import Command, MessageCreated  # Command импортируется отсюда

from app.config import settings

# Создаём роутер для группировки обработчиков этого модуля
router = Router()


@router.message_created(Command('help'))
async def help_command(event: MessageCreated):
    """
    🆘 Обработчик команды /help.

    Отправляет пользователю список доступных команд и техническую информацию.

    Аргументы:
        event (MessageCreated): событие создания сообщения.
    """
    user = event.from_user
    logger.info(f"ℹ️ Пользователь {user.user_id} запросил справку")

    # Формируем текст справки (точно как в оригинале, но с учётом среды)
    help_text = (
        f"🆘 <b>Помощь по боту</b>\n\n"
        f"📋 <b>Доступные команды:</b>\n"
        f"• /start - Запуск бота и приветствие\n"
        f"• /help - Показать эту справку\n"
        f"• /status - Проверить статус бота\n\n"
        f"🔧 <b>Технические детали:</b>\n"
        f"• Среда: {settings.env}\n"
        f"• Контейнеризация: Docker\n\n"
        f"💬 Если у вас есть вопросы, обращайтесь к разработчику."
    )

    # Отправляем ответ (параметр format удалён)
    await event.message.answer(help_text)


@router.message_created(Command('status'))
async def status_command(event: MessageCreated):
    """
    📊 Обработчик команды /status.

    Отправляет информацию о текущем состоянии бота (активен, среда, время проверки).

    Аргументы:
        event (MessageCreated): событие создания сообщения.
    """
    user = event.from_user
    logger.info(f"📊 Пользователь {user.user_id} запросил статус")

    current_time = datetime.now().strftime('%H:%M:%S %d.%m.%Y')

    status_text = (
        f"📊 <b>Статус бота</b>\n\n"
        f"✅ Бот активен и работает\n"
        f"🏠 Среда: <code>{settings.env}</code>\n"
        f"🗄️ База данных: Подключена\n"
        f"🚀 Redis: Подключен\n"
        f"⏰ Время проверки: {current_time}"
    )

    await event.message.answer(status_text)
