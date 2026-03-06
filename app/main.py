"""
Главный файл бота для MAX (maxbot)
"""
import asyncio
import sys
from loguru import logger

from maxbot import Bot, Dispatcher

from app.config import settings
from app.handlers import setup_routers
from app.database import db
from app.services import iiko_service


async def on_startup() -> None:
    """Действия при запуске бота"""
    try:
        await db.create_tables()
        await db.update_bot_stats()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        sys.exit(1)

    try:
        await iiko_service.init_iiko_client()
        logger.info("✅ iiko client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize iiko client: {e}")
        sys.exit(1)


async def on_shutdown() -> None:
    """Действия при остановке бота"""
    logger.info("🛑 Bot is shutting down...")
    await iiko_service.close_iiko_client()


async def main() -> None:
    """Главная функция"""
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        colorize=True
    )

    logger.info("🎯 Starting MAX Bot with maxbot...")

    # Создаём бота
    bot = Bot(token=settings.bot_token)

    # Создаём диспетчер (внутри создастся in-memory хранилище FSMStorage)
    dp = Dispatcher(bot)

    # Подключаем роутеры
    setup_routers(dp)

    # Выполняем действия при старте
    await on_startup()

    try:
        # Запускаем polling
        logger.info("🚀 Bot started polling")
        await dp.run_polling()
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
    finally:
        await on_shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Application terminated by user")
