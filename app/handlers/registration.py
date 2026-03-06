"""
Обработчики процесса регистрации: согласие с правилами, получение контакта и анкетирование
"""

from datetime import datetime, timezone

from loguru import logger

from maxbot.router import Router
from maxbot.types import Message, Callback
# используем только для payload, можно обойтись без фильтра, но оставим для простоты
from maxbot.filters import F

from app.database import db
from app.keyboards.registration import (
    get_contact_keyboard,
    get_gender_keyboard,
    get_notifications_keyboard,
    get_edit_choice_keyboard
)
from app.states.registration import Registration
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


# ---------- Обработчик нажатия на кнопку "Согласен" ----------
@router.callback()
async def process_rules_accept(callback: Callback):
    # Проверяем, что мы в нужном состоянии и нажата правильная кнопка
    current_state = await callback.get_state()
    if current_state != Registration.waiting_for_rules_consent.full_name():
        return
    if callback.payload != "accept_rules":
        return

    bot = callback.dispatcher.bot
    user_id = callback.user.id
    logger.info(f"Пользователь {user_id} принял согласие с правилами")

    await db.update_user(
        user_id,
        rules_accepted=True,
        rules_accepted_at=datetime.now(timezone.utc)
    )

    await bot.answer_callback(callback.callback_id, "Спасибо! Правила приняты.")
    # Убираем клавиатуру из сообщения
    await bot.update_message(
        message_id=callback.message.id,
        text=callback.message.text,
        reply_markup=None
    )

    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="✅ Отлично! Правила приняты. Теперь, чтобы подключиться к программе лояльности, "
             "нажми кнопку «📱 Поделиться контактом».",
        reply_markup=get_contact_keyboard()
    )
    await callback.set_state(Registration.waiting_for_contact)


# ---------- Обработчик получения контакта ----------
@router.message()
async def process_contact(message: Message):
    # Проверяем состояние
    current_state = await message.get_state()
    if current_state != Registration.waiting_for_contact.full_name():
        return

    bot = message.dispatcher.bot
    # Проверяем, что в сообщении есть контакт
    if not message.attachments or not any(att.type == "contact" for att in message.attachments):
        # Если контакта нет – напоминаем
        await bot.send_message(
            chat_id=message.chat.id,
            text="📱 Пожалуйста, нажмите кнопку «Поделиться контактом» на клавиатуре, "
                 "чтобы отправить свой номер телефона."
        )
        return

    contact_att = next((att for att in message.attachments if att.type == "contact"), None)
    if not contact_att:
        return

    phone = contact_att.payload.get("phoneNumber")
    if not phone:
        logger.error(f"Не удалось извлечь номер из контакта: {contact_att}")
        return

    user_id = message.sender.id
    logger.info(f"Пользователь user_id={user_id} отправил контакт")

    if not phone.startswith('+'):
        phone = '+' + phone

    await db.update_user(user_id, phone_number=phone)

    await bot.send_message(
        chat_id=message.chat.id,
        text="✅ Спасибо! Номер телефона сохранён.\n\n"
             "✍️ Теперь, пожалуйста, напишите ваше имя.",
        reply_markup=None
    )
    await message.set_state(Registration.waiting_for_first_name)


# ---------- Обработчик ввода имени ----------
@router.message()
async def process_first_name(message: Message):
    current_state = await message.get_state()
    if current_state != Registration.waiting_for_first_name.full_name():
        return

    bot = message.dispatcher.bot
    if not message.text:
        await bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите имя текстовым сообщением."
        )
        return

    user_id = message.sender.id
    first_name_text = message.text.strip()
    logger.info(f"Пользователь user_id={user_id} вводит имя: '{first_name_text}'")

    is_valid, error_message = await validate_first_name(first_name_text)
    if not is_valid:
        await bot.send_message(chat_id=message.chat.id, text=error_message)
        return

    first_name_cleaned = await clean_name(first_name_text)
    await db.update_user(user_id, first_name_input=first_name_cleaned)

    await bot.send_message(
        chat_id=message.chat.id,
        text="✅ Спасибо! Теперь напишите вашу фамилию."
    )
    await message.set_state(Registration.waiting_for_last_name)


# ---------- Обработчик ввода фамилии ----------
@router.message()
async def process_last_name(message: Message):
    current_state = await message.get_state()
    if current_state != Registration.waiting_for_last_name.full_name():
        return

    bot = message.dispatcher.bot
    if not message.text:
        await bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите фамилию текстовым сообщением."
        )
        return

    user_id = message.sender.id
    last_name_text = message.text.strip()
    logger.info(f"Пользователь user_id={user_id} вводит фамилию: '{last_name_text}'")

    is_valid, error_message = await validate_last_name(last_name_text)
    if not is_valid:
        await bot.send_message(chat_id=message.chat.id, text=error_message)
        return

    last_name_cleaned = await clean_name(last_name_text)
    await db.update_user(user_id, last_name_input=last_name_cleaned)

    await bot.send_message(
        chat_id=message.chat.id,
        text="👍 Отлично! Теперь укажите ваш пол:",
        reply_markup=get_gender_keyboard()
    )
    await message.set_state(Registration.waiting_for_gender)


# ---------- Обработчик выбора пола ----------
@router.callback()
async def process_gender(callback: Callback):
    current_state = await callback.get_state()
    if current_state != Registration.waiting_for_gender.full_name():
        return
    if callback.payload not in ["gender_male", "gender_female"]:
        return

    bot = callback.dispatcher.bot
    user_id = callback.user.id
    gender_value = "male" if callback.payload == "gender_male" else "female"
    gender_text = "мужской" if gender_value == "male" else "женский"
    logger.info(f"Пользователь user_id={user_id} выбрал пол: {gender_text}")

    await db.update_user(user_id, gender=gender_value)

    await bot.answer_callback(callback.callback_id, "")
    await bot.update_message(
        message_id=callback.message.id,
        text=callback.message.text,
        reply_markup=None
    )
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="✅ Спасибо! Теперь укажите вашу дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990)."
    )
    await callback.set_state(Registration.waiting_for_birth_date)


# ---------- Обработчик ввода даты рождения ----------
@router.message()
async def process_birth_date(message: Message):
    current_state = await message.get_state()
    if current_state != Registration.waiting_for_birth_date.full_name():
        return

    bot = message.dispatcher.bot
    if not message.text:
        await bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите дату текстовым сообщением."
        )
        return

    user_id = message.sender.id
    text = message.text.strip()
    logger.info(f"Пользователь user_id={user_id} вводит дату рождения: '{text}'")

    is_valid, error_message = await validate_birth_date(text)
    if not is_valid:
        await bot.send_message(chat_id=message.chat.id, text=error_message)
        return

    birth = datetime.strptime(text, "%d.%m.%Y").date()
    await db.update_user(user_id, birth_date=birth)

    await bot.send_message(
        chat_id=message.chat.id,
        text="✅ Спасибо! Дата рождения сохранена.\n\n"
             "📧 Теперь, пожалуйста, укажите ваш адрес электронной почты."
    )
    await message.set_state(Registration.waiting_for_email)


# ---------- Обработчик ввода email ----------
@router.message()
async def process_email(message: Message):
    current_state = await message.get_state()
    if current_state != Registration.waiting_for_email.full_name():
        return

    bot = message.dispatcher.bot
    if not message.text:
        await bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите почту текстовым сообщением."
        )
        return

    user_id = message.sender.id
    email = message.text.strip()
    logger.info(f"Пользователь user_id={user_id} вводит email: '{email}'")

    is_valid, error_message = await validate_email(email)
    if not is_valid:
        await bot.send_message(chat_id=message.chat.id, text=error_message)
        return

    await db.update_user(user_id, email=email)

    # Показываем анкету для подтверждения
    await show_profile_review_util(message, Registration.waiting_for_review)


# ---------- Обработчики ревью анкеты ----------
@router.callback()
async def process_review(callback: Callback):
    current_state = await callback.get_state()
    if current_state != Registration.waiting_for_review.full_name():
        return

    bot = callback.dispatcher.bot
    if callback.payload == "review_correct":
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
        await callback.set_state(Registration.waiting_for_notifications_consent)

    elif callback.payload == "review_edit":
        await bot.answer_callback(callback.callback_id, "")
        text = "🔧 Выберите, что хотите исправить:"
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            reply_markup=get_edit_choice_keyboard()
        )
        await callback.set_state(Registration.waiting_for_edit_choice)


# ---------- Обработчик выбора поля для редактирования ----------
@router.callback()
async def process_edit_choice(callback: Callback):
    current_state = await callback.get_state()
    if current_state != Registration.waiting_for_edit_choice.full_name():
        return

    bot = callback.dispatcher.bot
    data = callback.payload
    await bot.answer_callback(callback.callback_id, "")

    if data == "edit_cancel":
        await show_profile_review_util(callback, Registration.waiting_for_review)
        return

    state_map = {
        "edit_first_name": (Registration.waiting_for_edit_first_name, "✍️ Введите новое имя:", None),
        "edit_last_name": (Registration.waiting_for_edit_last_name, "✍️ Введите новую фамилию:", None),
        "edit_gender": (Registration.waiting_for_edit_gender, "Выберите ваш пол:", get_gender_keyboard()),
        "edit_birth_date": (Registration.waiting_for_edit_birth_date, "📅 Введите новую дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990):", None),
        "edit_email": (Registration.waiting_for_edit_email, "📧 Введите новый email:", None),
    }

    if data in state_map:
        new_state, text, keyboard = state_map[data]
        if keyboard:
            await bot.update_message(
                message_id=callback.message.id,
                text=text,
                reply_markup=keyboard
            )
        else:
            await bot.update_message(
                message_id=callback.message.id,
                text=text
            )
        await callback.set_state(new_state)
    else:
        await show_profile_review_util(callback, Registration.waiting_for_review)


# ---------- Редактирование имени ----------
@router.message()
async def process_edit_first_name(message: Message):
    current_state = await message.get_state()
    if current_state != Registration.waiting_for_edit_first_name.full_name():
        return

    bot = message.dispatcher.bot
    if not message.text:
        await bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите имя текстовым сообщением."
        )
        return

    user_id = message.sender.id
    first_name_text = message.text.strip()
    is_valid, error_message = await validate_first_name(first_name_text)
    if not is_valid:
        await bot.send_message(chat_id=message.chat.id, text=error_message)
        return

    first_name_cleaned = await clean_name(first_name_text)
    await db.update_user(user_id, first_name_input=first_name_cleaned)
    await show_profile_review_util(message, Registration.waiting_for_review)


# ---------- Редактирование фамилии ----------
@router.message()
async def process_edit_last_name(message: Message):
    current_state = await message.get_state()
    if current_state != Registration.waiting_for_edit_last_name.full_name():
        return

    bot = message.dispatcher.bot
    if not message.text:
        await bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите фамилию текстовым сообщением."
        )
        return

    user_id = message.sender.id
    last_name_text = message.text.strip()
    is_valid, error_message = await validate_last_name(last_name_text)
    if not is_valid:
        await bot.send_message(chat_id=message.chat.id, text=error_message)
        return

    last_name_cleaned = await clean_name(last_name_text)
    await db.update_user(user_id, last_name_input=last_name_cleaned)
    await show_profile_review_util(message, Registration.waiting_for_review)


# ---------- Редактирование пола ----------
@router.callback()
async def process_edit_gender(callback: Callback):
    current_state = await callback.get_state()
    if current_state != Registration.waiting_for_edit_gender.full_name():
        return
    if callback.payload not in ["gender_male", "gender_female"]:
        return

    bot = callback.dispatcher.bot
    user_id = callback.user.id
    gender = "male" if callback.payload == "gender_male" else "female"
    await db.update_user(user_id, gender=gender)
    await bot.answer_callback(callback.callback_id, "✅ Пол сохранён.")
    await show_profile_review_util(callback, Registration.waiting_for_review)


# ---------- Редактирование даты рождения ----------
@router.message()
async def process_edit_birth_date(message: Message):
    current_state = await message.get_state()
    if current_state != Registration.waiting_for_edit_birth_date.full_name():
        return

    bot = message.dispatcher.bot
    if not message.text:
        await bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите дату текстовым сообщением."
        )
        return

    user_id = message.sender.id
    text = message.text.strip()
    is_valid, error_message = await validate_birth_date(text)
    if not is_valid:
        await bot.send_message(chat_id=message.chat.id, text=error_message)
        return

    birth = datetime.strptime(text, "%d.%m.%Y").date()
    await db.update_user(user_id, birth_date=birth)
    await show_profile_review_util(message, Registration.waiting_for_review)


# ---------- Редактирование email ----------
@router.message()
async def process_edit_email(message: Message):
    current_state = await message.get_state()
    if current_state != Registration.waiting_for_edit_email.full_name():
        return

    bot = message.dispatcher.bot
    if not message.text:
        await bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите почту текстовым сообщением."
        )
        return

    user_id = message.sender.id
    email = message.text.strip()
    is_valid, error_message = await validate_email(email)
    if not is_valid:
        await bot.send_message(chat_id=message.chat.id, text=error_message)
        return

    await db.update_user(user_id, email=email)
    await show_profile_review_util(message, Registration.waiting_for_review)


# ---------- Обработчик согласия на уведомления ----------
@router.callback()
async def process_notifications_consent(callback: Callback):
    current_state = await callback.get_state()
    if current_state != Registration.waiting_for_notifications_consent.full_name():
        return
    if callback.payload not in ["notify_yes", "notify_no"]:
        return

    bot = callback.dispatcher.bot
    user_id = callback.user.id
    notifications_allowed = (callback.payload == "notify_yes")
    choice_text = "согласился на уведомления" if notifications_allowed else "отказался от уведомлений"
    logger.info(f"Пользователь user_id={user_id} {choice_text}")

    await db.update_user(
        user_id,
        notifications_allowed=notifications_allowed,
        notifications_allowed_at=datetime.now(timezone.utc)
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

    await callback.set_state(Registration.waiting_for_iiko_registration)
    await sync_user_with_iiko(callback, user)


# ---------- Обработчик повторной попытки регистрации в iiko ----------
@router.callback()
async def retry_iiko_registration(callback: Callback):
    current_state = await callback.get_state()
    if current_state != Registration.waiting_for_iiko_registration.full_name():
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