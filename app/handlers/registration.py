"""
Обработчики процесса регистрации пользователя
===============================================
Этот модуль содержит все обработчики, связанные с регистрацией нового пользователя.
Он реализует конечный автомат (FSM) с состояниями, определёнными в `app.states.registration`.

Последовательность шагов:
1. Принятие правил (кнопка «Согласен»).
2. Получение номера телефона (кнопка «Поделиться контактом»).
3. Ввод имени.
4. Ввод фамилии.
5. Выбор пола.
6. Ввод даты рождения.
7. Ввод email.
8. Показ анкеты для подтверждения.
9. Возможность редактирования любого поля.
10. Согласие на уведомления.
11. Синхронизация с iiko.
"""

from datetime import datetime, timezone
from loguru import logger

from maxapi import Router
from maxapi.types import MessageCreated, MessageCallback
from maxapi.context import MemoryContext

from app.database import db
from app.states.registration import Registration
from app.keyboards.registration import (
    get_contact_keyboard,
    get_gender_keyboard,
    get_notifications_keyboard,
    get_edit_choice_keyboard,
)
from app.utils.validation import (
    validate_first_name,
    validate_last_name,
    validate_birth_date,
    validate_email,
    clean_name,
)
from app.utils.profile import show_profile_review
from app.services.user_sync import sync_user_with_iiko
from app.utils.vcf_parser import extract_phone_from_vcf

router = Router()


@router.message_callback(Registration.waiting_for_rules_consent)
async def process_rules_accept(event: MessageCallback, context: MemoryContext) -> None:
    if event.callback.payload != "accept_rules":
        return

    user_id = event.from_user.user_id
    logger.info(f"👤 Пользователь {user_id} принял согласие с правилами")

    await db.update_user(
        user_id,
        rules_accepted=True,
        rules_accepted_at=datetime.now(timezone.utc)
    )

    await event.answer("Спасибо! Правила приняты.")

    await event.message.edit_text(
        text=event.message.body.text,          # <-- исправлено
        attachments=[]
    )

    await event.message.answer(
        text="✅ Отлично! Правила приняты. Теперь, чтобы подключиться к программе лояльности, "
             "нажми кнопку «📱 Поделиться контактом».",
        attachments=[get_contact_keyboard()]
    )
    await context.set_state(Registration.waiting_for_contact)


@router.message_created(Registration.waiting_for_contact)
async def process_contact(event: MessageCreated, context: MemoryContext) -> None:
    """
    Обрабатывает получение контакта от пользователя.
    Извлекает номер телефона из VCF-вложения, сохраняет в БД и переводит
    пользователя в состояние ожидания имени.
    """
    if not event.message.body.attachments:
        await event.message.answer(
            text="📱 Пожалуйста, нажмите кнопку «Поделиться контактом» на клавиатуре."
        )
        return

    contact_att = next(
        (att for att in event.message.body.attachments if att.type == "contact"),
        None
    )
    if not contact_att:
        await event.message.answer(
            text="❌ Не удалось найти контакт. Пожалуйста, используйте кнопку."
        )
        return

    phone = None
    if hasattr(contact_att, 'payload') and hasattr(contact_att.payload, 'vcf_info'):
        phone = extract_phone_from_vcf(contact_att.payload.vcf_info)

    if not phone:
        logger.error(f"❌ Не удалось извлечь номер из контакта. Вложение: {contact_att}")
        await event.message.answer(
            text="❌ Не удалось получить номер телефона. Попробуйте ещё раз."
        )
        return

    if not phone.startswith('+'):
        phone = '+' + phone

    user_id = event.from_user.user_id
    await db.update_user(user_id, phone_number=phone)
    logger.info(f"✅ Пользователь {user_id} отправил контакт, номер сохранён: {phone}")

    await event.message.answer(
        text="✅ Спасибо! Номер телефона сохранён.\n\n"
             "✍️ Теперь, пожалуйста, напишите ваше имя."
    )
    await context.set_state(Registration.waiting_for_first_name)


@router.message_created(Registration.waiting_for_first_name)
async def process_first_name(event: MessageCreated, context: MemoryContext) -> None:
    if not event.message.body.text:                      # <-- исправлено
        await event.message.answer(
            text="✍️ Пожалуйста, введите имя текстовым сообщением."
        )
        return

    user_id = event.from_user.user_id
    first_name_text = event.message.body.text.strip()    # <-- исправлено
    logger.info(f"👤 Пользователь user_id={user_id} вводит имя: '{first_name_text}'")

    is_valid, error_message = await validate_first_name(first_name_text)
    if not is_valid:
        await event.message.answer(text=error_message)
        return

    first_name_cleaned = await clean_name(first_name_text)
    await db.update_user(user_id, first_name_input=first_name_cleaned)

    await event.message.answer(
        text="✅ Спасибо! Теперь напишите вашу фамилию."
    )
    await context.set_state(Registration.waiting_for_last_name)


@router.message_created(Registration.waiting_for_last_name)
async def process_last_name(event: MessageCreated, context: MemoryContext) -> None:
    if not event.message.body.text:                      # <-- исправлено
        await event.message.answer(
            text="✍️ Пожалуйста, введите фамилию текстовым сообщением."
        )
        return

    user_id = event.from_user.user_id
    last_name_text = event.message.body.text.strip()    # <-- исправлено
    logger.info(f"👤 Пользователь user_id={user_id} вводит фамилию: '{last_name_text}'")

    is_valid, error_message = await validate_last_name(last_name_text)
    if not is_valid:
        await event.message.answer(text=error_message)
        return

    last_name_cleaned = await clean_name(last_name_text)
    await db.update_user(user_id, last_name_input=last_name_cleaned)

    await event.message.answer(
        text="👍 Отлично! Теперь укажите ваш пол:",
        attachments=[get_gender_keyboard()]
    )
    await context.set_state(Registration.waiting_for_gender)


@router.message_callback(Registration.waiting_for_gender)
async def process_gender(event: MessageCallback, context: MemoryContext) -> None:
    if event.callback.payload not in ["gender_male", "gender_female"]:
        return

    user_id = event.from_user.user_id
    gender_value = "male" if event.callback.payload == "gender_male" else "female"
    gender_text = "мужской" if gender_value == "male" else "женский"
    logger.info(f"👤 Пользователь user_id={user_id} выбрал пол: {gender_text}")

    await db.update_user(user_id, gender=gender_value)

    await event.answer("")
    await event.message.edit_text(
        text=event.message.body.text,          # <-- исправлено
        attachments=[]
    )

    await event.message.answer(
        text="✅ Спасибо! Теперь укажите вашу дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990)."
    )
    await context.set_state(Registration.waiting_for_birth_date)


@router.message_created(Registration.waiting_for_birth_date)
async def process_birth_date(event: MessageCreated, context: MemoryContext) -> None:
    if not event.message.body.text:                      # <-- исправлено
        await event.message.answer(
            text="✍️ Пожалуйста, введите дату текстовым сообщением."
        )
        return

    user_id = event.from_user.user_id
    text = event.message.body.text.strip()                # <-- исправлено
    logger.info(f"👤 Пользователь user_id={user_id} вводит дату рождения: '{text}'")

    is_valid, error_message = await validate_birth_date(text)
    if not is_valid:
        await event.message.answer(text=error_message)
        return

    from datetime import datetime
    birth = datetime.strptime(text, "%d.%m.%Y").date()
    await db.update_user(user_id, birth_date=birth)

    await event.message.answer(
        text="✅ Спасибо! Дата рождения сохранена.\n\n"
             "📧 Теперь, пожалуйста, укажите ваш адрес электронной почты."
    )
    await context.set_state(Registration.waiting_for_email)


@router.message_created(Registration.waiting_for_email)
async def process_email(event: MessageCreated, context: MemoryContext) -> None:
    if not event.message.body.text:                      # <-- исправлено
        await event.message.answer(
            text="✍️ Пожалуйста, введите почту текстовым сообщением."
        )
        return

    user_id = event.from_user.user_id
    email = event.message.body.text.strip()               # <-- исправлено
    logger.info(f"👤 Пользователь user_id={user_id} вводит email: '{email}'")

    is_valid, error_message = await validate_email(email)
    if not is_valid:
        await event.message.answer(text=error_message)
        return

    await db.update_user(user_id, email=email)

    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.message_callback(Registration.waiting_for_review)
async def process_review(event: MessageCallback, context: MemoryContext) -> None:
    if event.callback.payload == "review_correct":
        await event.answer("")
        await event.message.edit_text(
            text=event.message.body.text,          # <-- исправлено
            attachments=[]
        )
        await event.message.answer(
            text="📢 Мы хотим радовать вас уникальными предложениями и акциями.\n"
                 "Ознакомьтесь с условиями получения уведомлений по ссылке ниже и сделайте выбор:",
            attachments=[get_notifications_keyboard()]
        )
        await context.set_state(Registration.waiting_for_notifications_consent)

    elif event.callback.payload == "review_edit":
        await event.answer("")
        text = "🔧 Выберите, что хотите исправить:"
        await event.message.edit_text(
            text=text,
            attachments=[get_edit_choice_keyboard()]
        )
        await context.set_state(Registration.waiting_for_edit_choice)


@router.message_callback(Registration.waiting_for_edit_choice)
async def process_edit_choice(event: MessageCallback, context: MemoryContext) -> None:
    payload = event.callback.payload
    await event.answer("")

    if payload == "edit_cancel":
        await show_profile_review(event, context, target_state=Registration.waiting_for_review)
        return

    mapping = {
        "edit_first_name": (Registration.waiting_for_edit_first_name, "✍️ Введите новое имя:", None),
        "edit_last_name": (Registration.waiting_for_edit_last_name, "✍️ Введите новую фамилию:", None),
        "edit_gender": (Registration.waiting_for_edit_gender, "Выберите ваш пол:", get_gender_keyboard()),
        "edit_birth_date": (Registration.waiting_for_edit_birth_date,
                            "📅 Введите новую дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990):", None),
        "edit_email": (Registration.waiting_for_edit_email, "📧 Введите новый email:", None),
    }

    if payload in mapping:
        new_state, text, keyboard = mapping[payload]
        await event.message.edit_text(
            text=text,
            attachments=[keyboard] if keyboard else []
        )
        await context.set_state(new_state)
    else:
        await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.message_created(Registration.waiting_for_edit_first_name)
async def process_edit_first_name(event: MessageCreated, context: MemoryContext) -> None:
    if not event.message.body.text:                      # <-- исправлено
        await event.message.answer(text="✍️ Пожалуйста, введите имя текстовым сообщением.")
        return

    user_id = event.from_user.user_id
    value = event.message.body.text.strip()               # <-- исправлено
    is_valid, error = await validate_first_name(value)
    if not is_valid:
        await event.message.answer(text=error)
        return

    cleaned = await clean_name(value)
    await db.update_user(user_id, first_name_input=cleaned)
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.message_created(Registration.waiting_for_edit_last_name)
async def process_edit_last_name(event: MessageCreated, context: MemoryContext) -> None:
    if not event.message.body.text:                      # <-- исправлено
        await event.message.answer(text="✍️ Пожалуйста, введите фамилию текстовым сообщением.")
        return

    user_id = event.from_user.user_id
    value = event.message.body.text.strip()               # <-- исправлено
    is_valid, error = await validate_last_name(value)
    if not is_valid:
        await event.message.answer(text=error)
        return

    cleaned = await clean_name(value)
    await db.update_user(user_id, last_name_input=cleaned)
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.message_callback(Registration.waiting_for_edit_gender)
async def process_edit_gender(event: MessageCallback, context: MemoryContext) -> None:
    if event.callback.payload not in ["gender_male", "gender_female"]:
        return

    user_id = event.from_user.user_id
    gender = "male" if event.callback.payload == "gender_male" else "female"
    await db.update_user(user_id, gender=gender)
    await event.answer("✅ Пол сохранён.")
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.message_created(Registration.waiting_for_edit_birth_date)
async def process_edit_birth_date(event: MessageCreated, context: MemoryContext) -> None:
    if not event.message.body.text:                      # <-- исправлено
        await event.message.answer(text="✍️ Пожалуйста, введите дату текстовым сообщением.")
        return

    user_id = event.from_user.user_id
    value = event.message.body.text.strip()               # <-- исправлено
    is_valid, error = await validate_birth_date(value)
    if not is_valid:
        await event.message.answer(text=error)
        return

    from datetime import datetime
    birth = datetime.strptime(value, "%d.%m.%Y").date()
    await db.update_user(user_id, birth_date=birth)
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.message_created(Registration.waiting_for_edit_email)
async def process_edit_email(event: MessageCreated, context: MemoryContext) -> None:
    if not event.message.body.text:                      # <-- исправлено
        await event.message.answer(text="✍️ Пожалуйста, введите почту текстовым сообщением.")
        return

    user_id = event.from_user.user_id
    value = event.message.body.text.strip()               # <-- исправлено
    is_valid, error = await validate_email(value)
    if not is_valid:
        await event.message.answer(text=error)
        return

    await db.update_user(user_id, email=value)
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.message_callback(Registration.waiting_for_notifications_consent)
async def process_notifications_consent(event: MessageCallback, context: MemoryContext) -> None:
    if event.callback.payload not in ["notify_yes", "notify_no"]:
        return

    user_id = event.from_user.user_id
    notifications_allowed = (event.callback.payload == "notify_yes")
    choice_text = "согласился на уведомления" if notifications_allowed else "отказался от уведомлений"
    logger.info(f"👤 Пользователь user_id={user_id} {choice_text}")

    await db.update_user(
        user_id,
        notifications_allowed=notifications_allowed,
        notifications_allowed_at=datetime.now(timezone.utc),
        is_legacy=False
    )

    await event.answer("")
    await event.message.edit_text(
        text=event.message.body.text,          # <-- исправлено
        attachments=[]
    )

    user = await db.get_user(user_id)
    if not user:
        await event.message.answer(text="❌ Ошибка загрузки пользователя")
        await context.clear()
        return

    await context.set_state(Registration.waiting_for_iiko_registration)
    await sync_user_with_iiko(event, user)


@router.message_callback(Registration.waiting_for_iiko_registration)
async def retry_iiko_registration(event: MessageCallback, context: MemoryContext) -> None:
    if event.callback.payload != "retry_iiko_registration":
        return

    await event.answer("")
    user = await db.get_user(event.from_user.user_id)
    if not user:
        await event.message.answer(text="❌ Ошибка загрузки пользователя")
        await context.clear()
        return

    await sync_user_with_iiko(event, user)
