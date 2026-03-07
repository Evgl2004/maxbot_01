"""
Обработчики процесса обновления для пользователей, перенесённых из старого бота (legacy)
=========================================================================================
Последовательность шагов:
1. Приветствие и согласие с правилами.
2. Проверка наличия всех обязательных полей (имя, фамилия, пол, дата рождения, email).
   - Если поле отсутствует или невалидно, оно запрашивается у пользователя.
3. После заполнения всех полей показывается анкета для подтверждения.
4. При необходимости можно отредактировать любое поле.
5. После подтверждения анкеты запрашивается согласие на уведомления.
6. Сохраняется согласие, снимается признак is_legacy, показывается главное меню.

Все хендлеры используют корректные методы maxapi:
- Текст сообщения: event.message.body.text
- Редактирование: event.bot.update_message с обязательным message_id
- Отправка клавиатур: attachments=[keyboard]
- Работа с FSM: context (MemoryContext) передаётся вторым параметром
- Ответ на callback: await event.answer("")
- Отправка простых сообщений: bot.send_message
"""

from datetime import datetime, timezone
import re
from typing import List, Union

from loguru import logger

from maxapi import Router
from maxapi.types import MessageCreated, MessageCallback
from maxapi.context import MemoryContext

from app.database import db
from app.keyboards.registration import (
    get_rules_keyboard,
    get_gender_keyboard,
    get_notifications_keyboard,
    get_edit_choice_keyboard,
)
from app.states.legacy import LegacyUpgrade
from app.utils.validation import (
    validate_first_name,
    validate_last_name,
    validate_birth_date,
    validate_email,
    clean_name,
)
from app.utils.profile import show_profile_review
from app.services.user_sync import sync_user_with_iiko

router = Router()


# ---------- Вспомогательные функции ----------
async def get_missing_fields(user) -> List[str]:
    """
    Определяет, какие обязательные поля у пользователя отсутствуют или невалидны.

    Args:
        user: объект пользователя из БД (модель User).

    Returns:
        List[str]: список строк-идентификаторов недостающих полей:
                   'first_name', 'last_name', 'gender', 'birth_date', 'email'.
    """
    missing = []

    # Имя
    if not user.first_name_input or not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', user.first_name_input):
        missing.append('first_name')
    # Фамилия
    if not user.last_name_input or not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', user.last_name_input):
        missing.append('last_name')
    # Пол
    if user.gender not in ['male', 'female']:
        missing.append('gender')
    # Дата рождения
    if not user.birth_date:
        missing.append('birth_date')
    else:
        today = datetime.now().date()
        age = (today.year
               - user.birth_date.year
               - ((today.month, today.day) < (user.birth_date.month, user.birth_date.day))
               )
        if age < 18 or age > 100:
            missing.append('birth_date')
    # Email
    if not user.email or not re.match(r'^[^@]+@[^@]+\.[^@]+$', user.email):
        missing.append('email')
    return missing


async def ask_next_field(event: Union[MessageCreated, MessageCallback],
                         context: MemoryContext, missing_fields: List[str]) -> None:
    """
    Задаёт пользователю следующий вопрос из списка missing_fields.
    Если список пуст – переходит к показу анкеты (show_profile_review).

    Args:
        event (Union[MessageCreated, MessageCallback]): событие (сообщение или callback),
        через которое отправляется ответ.
        context (MemoryContext): контекст FSM для сохранения данных и смены состояния.
        missing_fields (List[str]): список недостающих полей.
    """
    if not missing_fields:
        # Все поля заполнены – показываем анкету
        await show_profile_review(event, context, target_state=LegacyUpgrade.waiting_for_review)
        return

    # Сохраняем оставшиеся поля в контексте (чтобы потом поочерёдно обрабатывать)
    await context.update_data(missing_fields=missing_fields)

    field = missing_fields[0]
    bot = event.bot

    if field == 'first_name':
        text = "✍️ Введите ваше имя:"
        await bot.send_message(chat_id=event.chat.id, text=text)
        await context.set_state(LegacyUpgrade.waiting_for_field)

    elif field == 'last_name':
        text = "✍️ Введите вашу фамилию:"
        await bot.send_message(chat_id=event.chat.id, text=text)
        await context.set_state(LegacyUpgrade.waiting_for_field)

    elif field == 'gender':
        if isinstance(event, MessageCallback):
            # Если это callback – редактируем текущее сообщение
            await event.bot.edit_message(
                message_id=event.message.body.mid,
                text="Выберите ваш пол:",
                attachments=[get_gender_keyboard()]
            )
            await event.answer("")
        else:
            # Если это новое сообщение – отправляем новое
            await event.message.answer(
                text="Выберите ваш пол:",
                attachments=[get_gender_keyboard()]
            )
        await context.set_state(LegacyUpgrade.waiting_for_field)

    elif field == 'birth_date':
        text = "📅 Введите вашу дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990):"
        await bot.send_message(chat_id=event.chat.id, text=text)
        await context.set_state(LegacyUpgrade.waiting_for_field)

    elif field == 'email':
        text = "📧 Введите ваш email:"
        await bot.send_message(chat_id=event.chat.id, text=text)
        await context.set_state(LegacyUpgrade.waiting_for_field)

    else:
        # Неизвестное поле – пропускаем
        missing_fields.pop(0)
        await ask_next_field(event, context, missing_fields)


# ---------- Начало обновления ----------
async def start_legacy_upgrade(message: MessageCreated, user):
    """
    Запускает процесс обновления для устаревшего пользователя.
    Вызывается из start.py, когда обнаружен пользователь с is_legacy=True.

    Args:
        message (MessageCreated): событие, инициировавшее старт
        user: объект пользователя из БД
    """
    logger.info(f"Запуск обновления для устаревшего пользователя user_id={user.user_id} (is_legacy={user.is_legacy})")
    bot = message.bot

    # Приветственное сообщение
    text = (
        "👋 Здравствуй, друг! Мы обновили бота и хотим убедиться, "
        "что твои данные актуальны, а также получить необходимые согласия. "
        "Это займёт всего пару минут."
    )
    await bot.send_message(chat_id=message.chat.id, text=text)

    # Показываем правила
    await bot.send_message(
        chat_id=message.chat.id,
        text="📜 Для начала нам необходимо получить твоё согласие на обработку персональных данных "
             "и согласие с политикой конфиденциальности.\n\n"
             "👉 Ознакомься с документами по ссылке ниже и нажми «✅ Согласен».",
        attachments=[get_rules_keyboard()]
    )
    await message.set_state(LegacyUpgrade.waiting_for_rules_consent)


# ---------- Обработчики состояний ----------
@router.message_callback(LegacyUpgrade.waiting_for_rules_consent)
async def process_rules_accept(event: MessageCallback, context: MemoryContext) -> None:
    """
    Обработчик нажатия кнопки «Согласен» на правилах.

    Сохраняет согласие, убирает клавиатуру и запускает проверку недостающих полей.
    """
    if event.callback.payload != "accept_rules":
        return

    user_id = event.user.user_id
    logger.info(f"Legacy пользователь {user_id} принял правила")

    await db.update_user(
        user_id,
        rules_accepted=True,
        rules_accepted_at=datetime.now(timezone.utc)
    )

    await event.answer("Спасибо! Правила приняты.")
    # Убираем клавиатуру – редактируем сообщение
    await event.bot.edit_message(
        message_id=event.message.body.mid,
        text=event.message.body.text,
        attachments=[]
    )

    user = await db.get_user(user_id)
    missing = await get_missing_fields(user)
    if missing:
        await ask_next_field(event, context, missing)
    else:
        # Если все поля уже заполнены, сразу показываем анкету
        await show_profile_review(event, context, target_state=LegacyUpgrade.waiting_for_review)


@router.message_created(LegacyUpgrade.waiting_for_field)
async def process_field_input(event: MessageCreated, context: MemoryContext) -> None:
    """
    Обрабатывает текстовый ввод для имени, фамилии, даты рождения или email.

    Определяет, какое поле сейчас ожидается (первое в списке missing_fields),
    валидирует введённое значение, сохраняет в БД и переходит к следующему полю.
    """
    if not event.message.body.text:
        await event.message.answer(
            text="✍️ Пожалуйста, введите значение текстовым сообщением."
        )
        return

    user_id = event.sender.user_id
    data_from_context = await context.get_data()
    missing_fields = data_from_context.get('missing_fields', [])
    if not missing_fields:
        await show_profile_review(event, context, target_state=LegacyUpgrade.waiting_for_review)
        return

    field = missing_fields[0]
    value = event.message.body.text.strip()
    bot = event.bot

    if field == 'first_name':
        is_valid, error_message = await validate_first_name(value)
        if not is_valid:
            await bot.send_message(chat_id=event.chat.id, text=error_message)
            return
        cleaned = await clean_name(value)
        await db.update_user(user_id, first_name_input=cleaned)
        missing_fields.pop(0)
        await ask_next_field(event, context, missing_fields)

    elif field == 'last_name':
        is_valid, error_message = await validate_last_name(value)
        if not is_valid:
            await bot.send_message(chat_id=event.chat.id, text=error_message)
            return
        cleaned = await clean_name(value)
        await db.update_user(user_id, last_name_input=cleaned)
        missing_fields.pop(0)
        await ask_next_field(event, context, missing_fields)

    elif field == 'birth_date':
        is_valid, error_message = await validate_birth_date(value)
        if not is_valid:
            await bot.send_message(chat_id=event.chat.id, text=error_message)
            return
        birth = datetime.strptime(value, "%d.%m.%Y").date()
        await db.update_user(user_id, birth_date=birth)
        missing_fields.pop(0)
        await ask_next_field(event, context, missing_fields)

    elif field == 'email':
        is_valid, error_message = await validate_email(value)
        if not is_valid:
            await bot.send_message(chat_id=event.chat.id, text=error_message)
            return
        await db.update_user(user_id, email=value)
        missing_fields.pop(0)
        await ask_next_field(event, context, missing_fields)

    else:
        # Неизвестное поле – пропускаем
        missing_fields.pop(0)
        await ask_next_field(event, context, missing_fields)


@router.message_callback(LegacyUpgrade.waiting_for_field)
async def process_gender_input(event: MessageCallback, context: MemoryContext) -> None:
    """
    Обрабатывает нажатие на кнопки выбора пола (мужской/женский) в состоянии ожидания поля.
    """
    if event.callback.payload not in ["gender_male", "gender_female"]:
        return

    user_id = event.user.user_id
    data_from_context = await context.get_data()
    missing_fields = data_from_context.get('missing_fields', [])
    if not missing_fields or missing_fields[0] != 'gender':
        await show_profile_review(event, context, target_state=LegacyUpgrade.waiting_for_review)
        return

    gender = "male" if event.callback.payload == "gender_male" else "female"
    await db.update_user(user_id, gender=gender)
    missing_fields.pop(0)

    await event.answer("✅ Пол сохранён.")
    await ask_next_field(event, context, missing_fields)


@router.message_callback(LegacyUpgrade.waiting_for_review)
async def process_review_correct(event: MessageCallback, context: MemoryContext) -> None:
    """
    Пользователь подтвердил, что данные верны. Переходим к согласию на уведомления.
    """
    if event.callback.payload != "review_correct":
        return

    await event.answer("")
    await event.bot.edit_message(
        message_id=event.message.body.mid,
        text=event.message.body.text,
        attachments=[]
    )

    await event.message.answer(
        text="📢 Мы хотим радовать вас уникальными предложениями и акциями.\n"
             "Ознакомьтесь с условиями получения уведомлений по ссылке ниже и сделайте выбор:",
        attachments=[get_notifications_keyboard()]
    )
    await context.set_state(LegacyUpgrade.waiting_for_notifications_consent)


@router.message_callback(LegacyUpgrade.waiting_for_review)
async def process_review_edit(event: MessageCallback, context: MemoryContext) -> None:
    """
    Пользователь хочет что-то изменить. Показываем меню выбора поля для редактирования.
    """
    if event.callback.payload != "review_edit":
        return

    await event.answer("")
    text = "🔧 Выберите, что хотите исправить:"
    await event.bot.edit_message(
        message_id=event.message.body.mid,
        text=text,
        attachments=[get_edit_choice_keyboard()]
    )
    await context.set_state(LegacyUpgrade.waiting_for_edit_choice)


@router.message_callback(LegacyUpgrade.waiting_for_edit_choice)
async def process_edit_choice(event: MessageCallback, context: MemoryContext) -> None:
    """
    Обрабатывает выбор пользователя в меню редактирования.
    Сохраняет выбранное поле в контексте и переводит в состояние ожидания ввода нового значения.
    Для поля 'пол' сразу показывает клавиатуру выбора.
    """
    payload = event.callback.payload
    await event.answer("")

    if payload == "edit_cancel":
        await show_profile_review(event, context, target_state=LegacyUpgrade.waiting_for_review)
        return

    # Сохраняем выбранное поле в контексте
    await context.update_data(edit_field=payload)

    if payload == "edit_first_name":
        text = "✍️ Введите новое имя:"
        await event.bot.edit_message(
            message_id=event.message.body.mid,
            text=text,
            attachments=[]
        )
        await context.set_state(LegacyUpgrade.waiting_for_edit_field)

    elif payload == "edit_last_name":
        text = "✍️ Введите новую фамилию:"
        await event.bot.edit_message(
            message_id=event.message.body.mid,
            text=text,
            attachments=[]
        )
        await context.set_state(LegacyUpgrade.waiting_for_edit_field)

    elif payload == "edit_gender":
        text = "Выберите ваш пол:"
        await event.bot.edit_message(
            message_id=event.message.body.mid,
            text=text,
            attachments=[get_gender_keyboard()]
        )
        await context.set_state(LegacyUpgrade.waiting_for_edit_field)

    elif payload == "edit_birth_date":
        text = "📅 Введите новую дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990):"
        await event.bot.edit_message(
            message_id=event.message.body.mid,
            text=text,
            attachments=[]
        )
        await context.set_state(LegacyUpgrade.waiting_for_edit_field)

    elif payload == "edit_email":
        text = "📧 Введите новый email:"
        await event.bot.edit_message(
            message_id=event.message.body.mid,
            text=text,
            attachments=[]
        )
        await context.set_state(LegacyUpgrade.waiting_for_edit_field)

    else:
        await show_profile_review(event, context, target_state=LegacyUpgrade.waiting_for_review)


@router.message_created(LegacyUpgrade.waiting_for_edit_field)
async def process_edit_field(event: MessageCreated, context: MemoryContext) -> None:
    """
    Обрабатывает текстовый ввод нового значения для редактируемого поля.
    """
    if not event.message.body.text:
        await event.message.answer(
            text="✍️ Пожалуйста, введите значение текстовым сообщением."
        )
        return

    user_id = event.sender.user_id
    context_data = await context.get_data()
    field = context_data.get('edit_field')
    value = event.message.body.text.strip()
    bot = event.bot

    if field == 'edit_first_name':
        is_valid, error_message = await validate_first_name(value)
        if not is_valid:
            await bot.send_message(chat_id=event.chat.id, text=error_message)
            return
        cleaned = await clean_name(value)
        await db.update_user(user_id, first_name_input=cleaned)

    elif field == 'edit_last_name':
        is_valid, error_message = await validate_last_name(value)
        if not is_valid:
            await bot.send_message(chat_id=event.chat.id, text=error_message)
            return
        cleaned = await clean_name(value)
        await db.update_user(user_id, last_name_input=cleaned)

    elif field == 'edit_birth_date':
        is_valid, error_message = await validate_birth_date(value)
        if not is_valid:
            await bot.send_message(chat_id=event.chat.id, text=error_message)
            return
        birth = datetime.strptime(value, "%d.%m.%Y").date()
        await db.update_user(user_id, birth_date=birth)

    elif field == 'edit_email':
        is_valid, error_message = await validate_email(value)
        if not is_valid:
            await bot.send_message(chat_id=event.chat.id, text=error_message)
            return
        await db.update_user(user_id, email=value)

    else:
        await show_profile_review(event, context, target_state=LegacyUpgrade.waiting_for_review)
        return

    await show_profile_review(event, context, target_state=LegacyUpgrade.waiting_for_review)


@router.message_callback(LegacyUpgrade.waiting_for_edit_field)
async def process_edit_gender(event: MessageCallback, context: MemoryContext) -> None:
    """
    Обрабатывает выбор нового пола при редактировании (кнопки).
    """
    if event.callback.payload not in ["gender_male", "gender_female"]:
        return

    user_id = event.user.user_id
    gender = "male" if event.callback.payload == "gender_male" else "female"
    await db.update_user(user_id, gender=gender)

    await event.answer("✅ Пол сохранён.")
    await show_profile_review(event, context, target_state=LegacyUpgrade.waiting_for_review)


@router.message_callback(LegacyUpgrade.waiting_for_notifications_consent)
async def process_notifications_consent(event: MessageCallback, context: MemoryContext) -> None:
    """
    Обрабатывает выбор пользователя по согласию на уведомления.
    Сохраняет выбор, снимает флаг is_legacy и запускает синхронизацию с iiko.
    """
    if event.callback.payload not in ["notify_yes", "notify_no"]:
        return

    user_id = event.user.user_id
    notifications_allowed = (event.callback.payload == "notify_yes")
    choice_text = "согласился на уведомления" if notifications_allowed else "отказался от уведомлений"
    logger.info(f"Legacy user {user_id} {choice_text}")

    await db.update_user(
        user_id,
        notifications_allowed=notifications_allowed,
        notifications_allowed_at=datetime.now(timezone.utc),
        is_legacy=False
    )

    await event.answer("")
    await event.bot.edit_message(
        message_id=event.message.body.mid,
        text=event.message.body.text,
        attachments=[]
    )

    user = await db.get_user(user_id)
    if not user:
        await event.message.answer(text="❌ Ошибка загрузки пользователя")
        await context.clear()
        return

    await context.set_state(LegacyUpgrade.waiting_for_iiko_registration)
    await sync_user_with_iiko(event, user)


@router.message_callback(LegacyUpgrade.waiting_for_iiko_registration)
async def retry_iiko_registration(event: MessageCallback, context: MemoryContext) -> None:
    """
    Повторная попытка синхронизации с iiko при ошибке.
    """
    if event.callback.payload != "retry_iiko_registration":
        return

    await event.answer("")
    user = await db.get_user(event.user.user_id)
    if not user:
        await event.message.answer(text="❌ Ошибка загрузки пользователя")
        await context.clear()
        return

    await sync_user_with_iiko(event, user)
