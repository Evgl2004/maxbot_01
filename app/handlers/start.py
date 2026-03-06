"""
Обработчик команды /start с проверкой регистрации и согласий
"""

from maxbot.router import Router
from maxbot.types import Message
from maxbot.filters import F  # или Command, если есть
from loguru import logger

from app.database import db
from app.keyboards.registration import get_rules_keyboard, get_contact_keyboard
from app.states.registration import Registration
from app.handlers.menu import show_main_menu
from app.handlers.legacy import start_legacy_upgrade
from app.utils import with_logging, with_user_save

router = Router()


@router.message(F.text == "/start")   # временно, пока нет Command
@with_logging
@with_user_save
async def start_command(message: Message):
    """
    Обработчик команды /start.
    Проверяет статус пользователя и направляет по нужному пути.
    """
    # Получаем данные пользователя из события
    user = message.sender
    user_id = user.id
    logger.info(f"Пользователь user_id={user_id} запустил бот")

    # Получаем полные данные пользователя из БД (декоратор уже сохранил/обновил)
    db_user = await db.get_user(user_id)
    if not db_user:
        logger.error(f"Пользователь user_id={user_id} не найден в БД")
        return

    # Проверка, является ли пользователь устаревшим
    if db_user.is_registered and db_user.is_legacy:
        logger.info(f"Устаревший пользователь user_id={user_id}, запускаем процесс обновления данных")
        await start_legacy_upgrade(message, db_user)  # state не передаём
        return

    # Проверка согласия с правилами
    if not db_user.rules_accepted:
        bot = message.dispatcher.bot
        await bot.send_message(
            chat_id=message.chat.id,
            text=(
                "👋 Здравствуй Друг!\n\n"
                "Добро пожаловать к нам в гости!\n\n"
                "📜 Для начала нам необходимо получить твоё согласие на обработку персональных данных "
                "и согласие с политикой конфиденциальности.\n\n"
                "👉 Ознакомься с документами по ссылке ниже и нажми «✅ Согласен»."
            ),
            reply_markup=get_rules_keyboard()
        )
        await message.set_state(Registration.waiting_for_rules_consent)
        return

    # Проверка завершённости регистрации
    if not db_user.is_registered:
        bot = message.dispatcher.bot
        await bot.send_message(
            chat_id=message.chat.id,
            text=(
                "📱 Чтобы подключиться к программе лояльности, нажми кнопку «Поделиться контактом».\n"
                "После этого мы будем знакомы чуть ближе."
            ),
            reply_markup=get_contact_keyboard()
        )
        await message.set_state(Registration.waiting_for_contact)
        return

    # Если регистрация завершена — показываем главное меню
    bot = message.dispatcher.bot
    await show_main_menu(
        chat_id=message.chat.id,
        bot=bot,
        user_name=db_user.first_name_input or "Гость"
        # state больше не передаём
    )
