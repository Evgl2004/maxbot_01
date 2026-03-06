"""
Обработчики процесса обновления для пользователей, перенесённых из старого бота (legacy).
Последовательность шагов:
1. Приветствие и согласие с правилами.
2. Проверка наличия всех обязательных полей (имя, фамилия, пол, дата рождения, email).
   - Если поле отсутствует или невалидно, оно запрашивается у пользователя.
3. После заполнения всех полей показывается анкета для подтверждения.
4. При необходимости можно отредактировать любое поле.
5. После подтверждения анкеты запрашивается согласие на уведомления.
6. Сохраняется согласие, снимается признак is_legacy, показывается главное меню.
"""

from datetime import datetime, timezone
import re
from typing import Union, List

from loguru import logger

from maxbot.router import Router
from maxbot.types import Message, Callback

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
    confirm_text
)
from app.utils.profile import show_profile_review as show_profile_review_util
from app.services.user_sync import sync_user_with_iiko

router = Router()


# ---------- Вспомогательные функции ----------
async def get_missing_fields(user) -> List[str]:
    """
    Определяет, какие обязательные поля у пользователя отсутствуют или невалидны.
    Возвращает список строк-идентификаторов: 'first_name', 'last_name', 'gender', 'birth_date', 'email'.
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
    # Дата рождения (проверка, что это date и возраст 18-100)
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


async def ask_next_field(event: Union[Message, Callback], missing_fields: List[str]):
    """
    Задаёт пользователю следующий вопрос из списка missing_fields.
    Если список пуст – переходит к показу анкеты (show_profile_review).
    """
    if not missing_fields:
        await show_profile_review_util(event, LegacyUpgrade.waiting_for_review)
        return

    # Сохраняем оставшиеся поля в данных состояния
    await event.update_data(missing_fields=missing_fields)

    field = missing_fields[0]
    bot = event.dispatcher.bot

    if field == 'first_name':
        text = "✍️ Введите ваше имя:"
        await bot.send_message(chat_id=event.chat.id, text=text)
        await event.set_state(LegacyUpgrade.waiting_for_field)
    elif field == 'last_name':
        text = "✍️ Введите вашу фамилию:"
        await bot.send_message(chat_id=event.chat.id, text=text)
        await event.set_state(LegacyUpgrade.waiting_for_field)
    elif field == 'gender':
        if isinstance(event, Callback):
            await bot.update_message(
                message_id=event.message.id,
                text="Выберите ваш пол:",
                reply_markup=get_gender_keyboard()
            )
            await bot.answer_callback(event.callback_id, "")
        else:
            await bot.send_message(
                chat_id=event.chat.id,
                text="Выберите ваш пол:",
                reply_markup=get_gender_keyboard()
            )
        await event.set_state(LegacyUpgrade.waiting_for_field)
    elif field == 'birth_date':
        text = "📅 Введите вашу дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990):"
        await bot.send_message(chat_id=event.chat.id, text=text)
        await event.set_state(LegacyUpgrade.waiting_for_field)
    elif field == 'email':
        text = "📧 Введите ваш email:"
        await bot.send_message(chat_id=event.chat.id, text=text)
        await event.set_state(LegacyUpgrade.waiting_for_field)
    else:
        # Неизвестное поле – пропускаем
        missing_fields.pop(0)
        await ask_next_field(event, missing_fields)


# ---------- Начало обновления ----------
async def start_legacy_upgrade(message: Message, user):
    """
    Запускает процесс обновления для устаревшего-пользователя.
    Вызывается из start.py, когда обнаружен пользователь с is_legacy=True.
    """
    logger.info(f"Запуск обновления для устаревшего пользователя user_id={user.id} (is_legacy={user.is_legacy})")
    bot = message.dispatcher.bot

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
        reply_markup=get_rules_keyboard()
    )
    await message.set_state(LegacyUpgrade.waiting_for_rules_consent)


# ---------- Обработчики состояний ----------
@router.callback()
async def process_rules_accept(callback: Callback):
    """
    Обработчик нажатия кнопки «Согласен» на правилах.
    """
    current_state = await callback.get_state()
    if current_state != LegacyUpgrade.waiting_for_rules_consent.full_name():
        return
    if callback.payload != "accept_rules":
        return

    user_id = callback.user.id
    logger.info(f"Устаревший пользователь user_id={user_id} принял правила")
    bot = callback.dispatcher.bot

    # Сохраняем согласие с датой
    await db.update_user(
        user_id,
        rules_accepted=True,
        rules_accepted_at=datetime.now(timezone.utc)
    )

    await bot.answer_callback(callback.callback_id, "Спасибо! Правила приняты.")
    await bot.update_message(
        message_id=callback.message.id,
        text=callback.message.text,
        reply_markup=None
    )

    # Получаем пользователя и список недостающих полей
    user = await db.get_user(user_id)
    missing = await get_missing_fields(user)
    if missing:
        await ask_next_field(callback, missing)
    else:
        # Если все поля уже заполнены, сразу показываем анкету
        await show_profile_review_util(callback, LegacyUpgrade.waiting_for_review)


# ---------- Обработка ввода полей ----------
@router.message()
async def process_field_input(message: Message):
    """
    Обрабатывает текстовый ввод для имени, фамилии, даты рождения или email.
    """
    current_state = await message.get_state()
    if current_state != LegacyUpgrade.waiting_for_field.full_name():
        return

    if not message.text:
        await message.dispatcher.bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите значение текстовым сообщением."
        )
        return

    user_id = message.sender.id
    data = await message.get_data()
    missing_fields = data.get('missing_fields', [])
    if not missing_fields:
        await show_profile_review_util(message, LegacyUpgrade.waiting_for_review)
        return

    field = missing_fields[0]
    value = message.text.strip()
    bot = message.dispatcher.bot

    # Валидация и сохранение с использованием общих функций
    if field == 'first_name':
        is_valid, error_message = await validate_first_name(value)
        if not is_valid:
            await bot.send_message(chat_id=message.chat.id, text=error_message)
            return
        cleaned = await clean_name(value)
        await db.update_user(user_id, first_name_input=cleaned)
        missing_fields.pop(0)
        await ask_next_field(message, missing_fields)

    elif field == 'last_name':
        is_valid, error_message = await validate_last_name(value)
        if not is_valid:
            await bot.send_message(chat_id=message.chat.id, text=error_message)
            return
        cleaned = await clean_name(value)
        await db.update_user(user_id, last_name_input=cleaned)
        missing_fields.pop(0)
        await ask_next_field(message, missing_fields)

    elif field == 'birth_date':
        is_valid, error_message = await validate_birth_date(value)
        if not is_valid:
            await bot.send_message(chat_id=message.chat.id, text=error_message)
            return
        birth = datetime.strptime(value, "%d.%m.%Y").date()
        await db.update_user(user_id, birth_date=birth)
        missing_fields.pop(0)
        await ask_next_field(message, missing_fields)

    elif field == 'email':
        is_valid, error_message = await validate_email(value)
        if not is_valid:
            await bot.send_message(chat_id=message.chat.id, text=error_message)
            return
        await db.update_user(user_id, email=value)
        missing_fields.pop(0)
        await ask_next_field(message, missing_fields)

    else:
        # Неизвестное поле – пропускаем
        missing_fields.pop(0)
        await ask_next_field(message, missing_fields)


# ---------- Обработка выбора пола (inline) ----------
@router.callback()
async def process_gender_input(callback: Callback):
    """
    Обрабатывает нажатие на кнопки выбора пола (мужской/женский) в состоянии ожидания поля.
    """
    current_state = await callback.get_state()
    if current_state != LegacyUpgrade.waiting_for_field.full_name():
        return
    if callback.payload not in ["gender_male", "gender_female"]:
        return

    user_id = callback.user.id
    data = await callback.get_data()
    missing_fields = data.get('missing_fields', [])
    if not missing_fields or missing_fields[0] != 'gender':
        await show_profile_review_util(callback, LegacyUpgrade.waiting_for_review)
        return

    gender = "male" if callback.payload == "gender_male" else "female"
    await db.update_user(user_id, gender=gender)
    missing_fields.pop(0)

    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "✅ Пол сохранён.")
    await ask_next_field(callback, missing_fields)


# ---------- Подтверждение анкеты ----------
@router.callback()
async def process_review_correct(callback: Callback):
    """
    Пользователь подтвердил, что данные верны. Переходим к согласию на уведомления.
    """
    current_state = await callback.get_state()
    if current_state != LegacyUpgrade.waiting_for_review.full_name():
        return
    if callback.payload != "review_correct":
        return

    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")
    await bot.update_message(
        message_id=callback.message.id,
        text=callback.message.text,
        reply_markup=None
    )
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="📢 Мы хотим радовать вас уникальными предложениями и акциями.\n"
             "Ознакомьтесь с условиями получения уведомлений по ссылке ниже и сделайте выбор:",
        reply_markup=get_notifications_keyboard()
    )
    await callback.set_state(LegacyUpgrade.waiting_for_notifications_consent)


@router.callback()
async def process_review_edit(callback: Callback):
    """
    Пользователь хочет что-то изменить. Показываем меню выбора поля для редактирования.
    """
    current_state = await callback.get_state()
    if current_state != LegacyUpgrade.waiting_for_review.full_name():
        return
    if callback.payload != "review_edit":
        return

    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")
    text = "🔧 Выберите, что хотите исправить:"
    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=get_edit_choice_keyboard()
    )
    await callback.set_state(LegacyUpgrade.waiting_for_edit_choice)


# ---------- Редактирование ----------
@router.callback()
async def process_edit_choice(callback: Callback):
    """
    Обрабатывает выбор пользователя в меню редактирования.
    Сохраняет выбранное поле в state и переводит в состояние ожидания ввода нового значения.
    Для поля 'пол' сразу показывает клавиатуру выбора.
    """
    current_state = await callback.get_state()
    if current_state != LegacyUpgrade.waiting_for_edit_choice.full_name():
        return

    data = callback.payload
    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")

    if data == "edit_cancel":
        await show_profile_review_util(callback, LegacyUpgrade.waiting_for_review)
        return

    # Сохраняем выбранное поле в state
    await callback.update_data(edit_field=data)

    if data == "edit_first_name":
        text = "✍️ Введите новое имя:"
        await bot.update_message(message_id=callback.message.id, text=text)
        await callback.set_state(LegacyUpgrade.waiting_for_edit_field)
    elif data == "edit_last_name":
        text = "✍️ Введите новую фамилию:"
        await bot.update_message(message_id=callback.message.id, text=text)
        await callback.set_state(LegacyUpgrade.waiting_for_edit_field)
    elif data == "edit_gender":
        text = "Выберите ваш пол:"
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            reply_markup=get_gender_keyboard()
        )
        await callback.set_state(LegacyUpgrade.waiting_for_edit_field)
    elif data == "edit_birth_date":
        text = "📅 Введите новую дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990):"
        await bot.update_message(message_id=callback.message.id, text=text)
        await callback.set_state(LegacyUpgrade.waiting_for_edit_field)
    elif data == "edit_email":
        text = "📧 Введите новый email:"
        await bot.update_message(message_id=callback.message.id, text=text)
        await callback.set_state(LegacyUpgrade.waiting_for_edit_field)
    else:
        await show_profile_review_util(callback, LegacyUpgrade.waiting_for_review)


@router.message()
async def process_edit_field(message: Message):
    """
    Обрабатывает текстовый ввод нового значения для редактируемого поля.
    """
    current_state = await message.get_state()
    if current_state != LegacyUpgrade.waiting_for_edit_field.full_name():
        return

    if not message.text:
        await message.dispatcher.bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите значение текстовым сообщением."
        )
        return

    user_id = message.sender.id
    data = await message.get_data()
    field = data.get('edit_field')
    value = message.text.strip()
    bot = message.dispatcher.bot

    if field == 'edit_first_name':
        is_valid, error_message = await validate_first_name(value)
        if not is_valid:
            await bot.send_message(chat_id=message.chat.id, text=error_message)
            return
        cleaned = await clean_name(value)
        await db.update_user(user_id, first_name_input=cleaned)
    elif field == 'edit_last_name':
        is_valid, error_message = await validate_last_name(value)
        if not is_valid:
            await bot.send_message(chat_id=message.chat.id, text=error_message)
            return
        cleaned = await clean_name(value)
        await db.update_user(user_id, last_name_input=cleaned)
    elif field == 'edit_birth_date':
        is_valid, error_message = await validate_birth_date(value)
        if not is_valid:
            await bot.send_message(chat_id=message.chat.id, text=error_message)
            return
        birth = datetime.strptime(value, "%d.%m.%Y").date()
        await db.update_user(user_id, birth_date=birth)
    elif field == 'edit_email':
        is_valid, error_message = await validate_email(value)
        if not is_valid:
            await bot.send_message(chat_id=message.chat.id, text=error_message)
            return
        await db.update_user(user_id, email=value)
    else:
        await show_profile_review_util(message, LegacyUpgrade.waiting_for_review)
        return

    await show_profile_review_util(message, LegacyUpgrade.waiting_for_review)


@router.callback()
async def process_edit_gender(callback: Callback):
    """
    Обрабатывает выбор нового пола при редактировании.
    """
    current_state = await callback.get_state()
    if current_state != LegacyUpgrade.waiting_for_edit_field.full_name():
        return
    if callback.payload not in ["gender_male", "gender_female"]:
        return

    user_id = callback.user.id
    gender = "male" if callback.payload == "gender_male" else "female"
    await db.update_user(user_id, gender=gender)

    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "✅ Пол сохранён.")
    await show_profile_review_util(callback, LegacyUpgrade.waiting_for_review)


# ---------- Согласие на уведомления ----------
@router.callback()
async def process_notifications_consent(callback: Callback):
    """
    Обрабатывает выбор пользователя по согласию на уведомления.
    Сохраняет выбор, снимает флаг is_legacy и запускает синхронизацию с iiko.
    """
    current_state = await callback.get_state()
    if current_state != LegacyUpgrade.waiting_for_notifications_consent.full_name():
        return
    if callback.payload not in ["notify_yes", "notify_no"]:
        return

    user_id = callback.user.id
    notifications_allowed = callback.payload == "notify_yes"
    choice_text = "согласился на уведомления" if notifications_allowed else "отказался от уведомлений"
    logger.info(f"Legacy user {user_id} {choice_text}")
    bot = callback.dispatcher.bot

    # Сохраняем согласие и снимаем признак legacy
    await db.update_user(
        user_id,
        notifications_allowed=notifications_allowed,
        notifications_allowed_at=datetime.now(timezone.utc),
        is_legacy=False
    )

    await bot.answer_callback(callback.callback_id, "")
    await bot.update_message(
        message_id=callback.message.id,
        text=callback.message.text,
        reply_markup=None
    )

    user = await db.get_user(user_id)
    if not user:
        await bot.send_message(chat_id=callback.message.chat.id, text="❌ Ошибка загрузки пользователя")
        await callback.reset_state()
        return

    await callback.set_state(LegacyUpgrade.waiting_for_iiko_registration)
    await sync_user_with_iiko(callback, user)


@router.callback()
async def retry_iiko_registration(callback: Callback):
    """
    Повторная попытка синхронизации с iiko при ошибке.
    """
    current_state = await callback.get_state()
    if current_state != LegacyUpgrade.waiting_for_iiko_registration.full_name():
        return
    if callback.payload != "retry_iiko_registration":
        return

    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")
    user = await db.get_user(callback.user.id)
    if not user:
        await bot.send_message(chat_id=callback.message.chat.id, text="❌ Ошибка загрузки пользователя")
        await callback.reset_state()
        return
    await sync_user_with_iiko(callback, user)
