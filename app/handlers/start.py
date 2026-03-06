"""
Обработчик команды /start с проверкой регистрации и согласий
===============================================================
При запуске бота проверяет статус пользователя и направляет по нужному пути:
- если не приняты правила → показываем правила и кнопку согласия
- если правила приняты, но регистрация не завершена → запрашиваем контакт
- если регистрация завершена → показываем главное меню
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

# Создаём роутер для группировки обработчиков этого модуля
router = Router()


@router.message_created(Command('start'))
async def start_command(event: MessageCreated, data: dict) -> None:
    """
    👋 Обработчик команды /start.

    Последовательность действий:
    1. Извлекаем пользователя из события.
    2. Получаем данные пользователя из БД (декораторы middleware уже сохранили/обновили).
    3. Если пользователь устаревший (is_legacy) – запускаем процесс обновления.
    4. Если не приняты правила – показываем правила и устанавливаем состояние.
    5. Если правила приняты, но регистрация не завершена – запрашиваем контакт.
    6. Иначе показываем главное меню.

    Аргументы:
        event (MessageCreated): событие создания сообщения
        data (dict): словарь с дополнительными данными, переданными middleware
                     В частности, там может быть ключ 'context' для работы с FSM
    """
    # Получаем контекст FSM (он может понадобиться для установки состояния)
    context: MemoryContext = data.get('context')
    if not context:
        logger.error("Контекст не найден")
        return

    # Получаем пользователя из события
    user = event.from_user
    user_id = user.user_id
    logger.info(f"Пользователь user_id={user_id} запустил бот")

    # Получаем полные данные пользователя из БД
    db_user = await db.get_user(user_id)
    if not db_user:
        logger.error(f"Пользователь user_id={user_id} не найден в БД")
        return

    # --- Проверка, является ли пользователь устаревшим ---
    if db_user.is_registered and db_user.is_legacy:
        logger.info(f"Устаревший пользователь user_id={user_id}, запускаем процесс обновления данных")
        # Вызываем обработчик legacy, передаём событие и пользователя
        await start_legacy_upgrade(event, db_user)
        return

    # --- Проверка согласия с правилами ---
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

    # --- Проверка завершённости регистрации ---
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

    # --- Если регистрация завершена — показываем главное меню ---
    await show_main_menu(
        chat_id=event.message.chat.id,
        bot=event.bot,
        user_name=db_user.first_name_input or "Гость"
    )
