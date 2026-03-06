import asyncio
from aiogram import Bot
from aiogram.types import BotCommandScopeDefault

BOT_TOKEN = "8377154477:AAGej4kxY5cZ93HLlWcIISGLkEN8FxpikM4"


async def clear_all():
    bot = Bot(token=BOT_TOKEN)
    # Список языков, для которых нужно удалить команды
    languages = ['ru', 'en', 'es', 'fr']  # добавьте все, что видели

    # Удаляем скоуп по умолчанию
    await bot.delete_my_commands(scope=BotCommandScopeDefault())

    # Удаляем для каждого языка
    for lang in languages:
        try:
            await bot.delete_my_commands(
                scope=BotCommandScopeDefault(),
                language_code=lang
            )
            print(f"Удалены команды для языка {lang}")
        except Exception as e:
            print(f"Ошибка для {lang}: {e}")

    # Проверяем результат
    print("Команды по умолчанию:", await bot.get_my_commands())
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(clear_all())