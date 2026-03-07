"""
Обработчик команды /start.
Проверяет статус пользователя и направляет по нужному пути.
"""

from loguru import logger

from maxapi import Router
from maxapi.types import Command, MessageCreated
from maxapi.context import MemoryContext

from app.database import db
from app.keyboards.registration import get_rules_keyboard, get_contact_keyboard
from app.states.registration import Registration
from app.handlers.menu import show_main_menu
from app.handlers.legacy import start_legacy_upgrade

router = Router()


@router.message_created(Command('start'))
async def start_command(event: MessageCreated, context: MemoryContext) -> None:
    """
    Обработчик команды /start.
    """
    user = event.from_user
    user_id = user.user_id
    logger.info(f"Пользователь user_id={user_id} запустил бот")

    db_user = await db.get_user(user_id)
    if not db_user:
        logger.error(f"Пользователь user_id={user_id} не найден в БД")
        return

    # Устаревший пользователь
    if db_user.is_registered and db_user.is_legacy:
        logger.info(f"Устаревший пользователь user_id={user_id}, запускаем процесс обновления")
        await start_legacy_upgrade(event, db_user)
        return

    # Правила не приняты
    if not db_user.rules_accepted:
        await event.message.answer(
            text=(
                "👋 Здравствуй Друг!\n\n"
                "Добро пожаловать к нам в гости!\n\n"
                "📜 Для начала нам необходимо получить твоё согласие на обработку персональных данных "
                "и согласие с политикой конфиденциальности.\n\n"
                "👉 Ознакомься с документами по ссылке ниже и нажми «✅ Согласен»."
            ),
            attachments=[get_rules_keyboard()]
        )
        await context.set_state(Registration.waiting_for_rules_consent)
        return

    # Регистрация не завершена
    if not db_user.is_registered:
        await event.message.answer(
            text=(
                "📱 Чтобы подключиться к программе лояльности, нажми кнопку «Поделиться контактом».\n"
                "После этого мы будем знакомы чуть ближе."
            ),
            attachments=[get_contact_keyboard()]
        )
        await context.set_state(Registration.waiting_for_contact)
        return

    # Всё готово – главное меню
    await show_main_menu(
        chat_id=event.message.chat.id,
        bot=event.bot,
        user_name=db_user.first_name_input or "Гость"
    )
