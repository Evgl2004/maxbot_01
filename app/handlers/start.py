"""
Обработчик команды /start.
Проверяет статус пользователя и направляет по нужному пути.
"""

from loguru import logger

from maxapi import Router
from maxapi.types import Command, MessageCreated
from maxapi.context import MemoryContext

from app.database import db
from app.states.registration import Registration
from app.handlers.menu import show_main_menu
from app.handlers.legacy import start_legacy_upgrade

from app.utils.fsm_helpers import get_prompt_for_state
from app.utils.profile import show_profile_review

router = Router()


@router.message_created(Command('start'))
async def start_command(event: MessageCreated, context: MemoryContext) -> None:
    """
    Обработчик команды /start.
    """
    logger.info(f"ТИП КОНТЕКСТА в start_command: {type(context).__name__}")
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
        # Передаём context, event, db_user
        await start_legacy_upgrade(event, db_user, context)
        return

    # Правила не приняты
    if not db_user.rules_accepted:
        # Проверяем, может быть уже есть состояние?
        current_state = await context.get_state()
        if current_state is None:
            await context.set_state(Registration.waiting_for_rules_consent)
            text, keyboard = get_prompt_for_state(Registration.waiting_for_rules_consent, context)
            await event.message.answer(text=text, attachments=[keyboard] if keyboard else [])
        else:
            # Если состояние уже есть, отправляем соответствующий запрос
            text, keyboard = get_prompt_for_state(current_state, context)
            if text == "__SHOW_PROFILE_REVIEW__":
                await show_profile_review(event, context, target_state=None)
            else:
                await event.message.answer(text=text, attachments=[keyboard] if keyboard else [])
        return

    # Регистрация не завершена
    if not db_user.is_registered:
        current_state = await context.get_state()
        if current_state is None:
            await context.set_state(Registration.waiting_for_contact)
            text, keyboard = get_prompt_for_state(Registration.waiting_for_contact, context)
            await event.message.answer(text=text, attachments=[keyboard] if keyboard else [])
        else:
            text, keyboard = get_prompt_for_state(current_state, context)
            if text == "__SHOW_PROFILE_REVIEW__":
                await show_profile_review(event, context, target_state=None)
            else:
                await event.message.answer(text=text, attachments=[keyboard] if keyboard else [])
        return

    # Всё готово – главное меню
    await show_main_menu(
        chat_id=event.message.recipient.chat_id,
        bot=event.bot,
        user_name=db_user.first_name_input or "Гость"
    )
