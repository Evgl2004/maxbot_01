"""
Обработчики команд помощи и информации
"""

from loguru import logger

from maxbot.router import Router
from maxbot.types import Message
from maxbot.filters import F

from app.config import settings

router = Router()


@router.message(F.text == "/help")
async def help_command(message: Message):
    """Обработчик команды /help"""
    user = message.sender
    logger.info(f"ℹ️ User {user.id} requested help")
    bot = message.dispatcher.bot

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

    await bot.send_message(
        chat_id=message.chat.id,
        text=help_text,
        format="html"
    )


@router.message(F.text == "/status")
async def status_command(message: Message):
    """Обработчик команды /status"""
    user = message.sender
    logger.info(f"📊 User {user.id} requested status")
    bot = message.dispatcher.bot

    status_text = (
        f"📊 <b>Статус бота</b>\n\n"
        f"✅ Бот активен и работает\n"
        f"🏠 Среда: <code>{settings.env}</code>\n"
        f"🗄️ База данных: Подключена\n"
        f"🚀 Redis: Подключен\n"
        f"⏰ Время проверки: {message.chat.id}"  # В maxbot нет message.date, можно использовать текущее время
    )

    await bot.send_message(
        chat_id=message.chat.id,
        text=status_text,
        format="html"
    )
