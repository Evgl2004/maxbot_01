"""
Обработчик команды /start и события bot_started.
Проверяет статус пользователя и направляет по нужному пути.
"""

from loguru import logger

from maxapi import Router
from maxapi.types import Command, MessageCreated, BotStarted
from maxapi.context import MemoryContext

from app.database import db
from app.states.registration import Registration
from app.handlers.menu import show_main_menu
from app.handlers.legacy import start_legacy_upgrade

from app.utils.fsm_helpers import get_prompt_for_state
from app.utils.profile import show_profile_review_by_ids

router = Router()


async def _handle_start_logic(user_id: int, chat_id: int, bot, context: MemoryContext) -> None:
    """
    Общая логика для обработки входа пользователя (команда /start или событие bot_started).

    Args:
        user_id (int): ID пользователя.
        chat_id (int): ID чата, куда отправлять ответы.
        bot: экземпляр бота.
        context (MemoryContext): контекст FSM.
    """
    db_user = await db.get_user(user_id)
    if not db_user:
        logger.error(f"Пользователь user_id={user_id} не найден в БД")
        return

    logger.info(
        f"=== _handle_start_logic: user_id={user_id}, "
        f"rules_accepted={db_user.rules_accepted}, "
        f"is_registered={db_user.is_registered}, "
        f"is_legacy={db_user.is_legacy}"
    )

    # Устаревший пользователь
    if db_user.is_registered and db_user.is_legacy:
        logger.info(f"Устаревший пользователь user_id={user_id}, запускаем процесс обновления")
        await start_legacy_upgrade(bot, chat_id, db_user, context)
        return

    # Правила не приняты
    if not db_user.rules_accepted:
        current_state = await context.get_state()
        logger.info(f"Правила не приняты, текущее состояние: {current_state}")
        # Если состояние существует и это не waiting_for_rules_consent, сбрасываем его
        if current_state is not None and current_state != Registration.waiting_for_rules_consent:
            logger.info(f"Обнаружено неожиданное состояние {current_state} при непринятых правилах, сбрасываем")
            await context.set_state(None)
            current_state = None
        if current_state is None:
            await context.set_state(Registration.waiting_for_rules_consent)
            text, keyboard = get_prompt_for_state(Registration.waiting_for_rules_consent, context)
            await bot.send_message(chat_id=chat_id, text=text, attachments=[keyboard] if keyboard else [])
            logger.info("Установлено состояние waiting_for_rules_consent")
        else:
            # здесь current_state обязательно waiting_for_rules_consent
            text, keyboard = get_prompt_for_state(current_state, context)
            if text == "__SHOW_PROFILE_REVIEW__":
                await show_profile_review_by_ids(bot, chat_id, user_id, context, target_state=None)
                logger.info(f"Вызван show_profile_review_by_ids для состояния {current_state}")
            else:
                await bot.send_message(chat_id=chat_id, text=text, attachments=[keyboard] if keyboard else [])
                logger.info(f"Отправлен запрос для состояния {current_state}")
        return

    # Регистрация не завершена
    if not db_user.is_registered:
        current_state = await context.get_state()
        logger.info(f"Регистрация не завершена, текущее состояние: {current_state}")
        if current_state is None:
            await context.set_state(Registration.waiting_for_contact)
            text, keyboard = get_prompt_for_state(Registration.waiting_for_contact, context)
            await bot.send_message(chat_id=chat_id, text=text, attachments=[keyboard] if keyboard else [])
            logger.info("Установлено состояние waiting_for_contact")
        else:
            text, keyboard = get_prompt_for_state(current_state, context)
            if text == "__SHOW_PROFILE_REVIEW__":
                await show_profile_review_by_ids(bot, chat_id, user_id, context, target_state=None)
                logger.info(f"Вызван show_profile_review_by_ids для состояния {current_state}")
            else:
                await bot.send_message(chat_id=chat_id, text=text, attachments=[keyboard] if keyboard else [])
                logger.info(f"Отправлен запрос для состояния {current_state}")
        return

    # Всё готово – главное меню
    logger.info("Всё готово, показываем главное меню")
    await show_main_menu(
        chat_id=chat_id,
        bot=bot,
        user_name=db_user.first_name_input or "Гость"
    )
    logger.info("Главное меню отправлено")


@router.message_created(Command('start'))
async def start_command(event: MessageCreated, context: MemoryContext) -> None:
    """
    Обработчик команды /start.
    """
    logger.info(f"ТИП КОНТЕКСТА в start_command: {type(context).__name__}")
    user_id = event.from_user.user_id
    chat_id = event.chat.chat_id
    logger.info(f"Пользователь user_id={user_id} запустил бот через /start")
    await _handle_start_logic(user_id, chat_id, event.bot, context)


@router.bot_started()
async def on_bot_started(event: BotStarted, context: MemoryContext) -> None:
    """
    Обработчик события bot_started (нажатие кнопки «Начать»).
    """
    logger.info(f"ТИП КОНТЕКСТА в on_bot_started: {type(context).__name__}")
    user_id = event.user.user_id
    chat_id = event.chat_id
    logger.info(f"Пользователь user_id={user_id} нажал кнопку «Начать»")
    await _handle_start_logic(user_id, chat_id, event.bot, context)
