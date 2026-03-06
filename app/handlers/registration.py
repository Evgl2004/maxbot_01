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

# Импорты из библиотеки maxapi
from maxapi import Router
from maxapi.types import MessageCreated, MessageCallback
from maxapi.context import MemoryContext

# Импорты наших модулей
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

# Создаём роутер для группировки обработчиков этого модуля
router = Router()


# ----------------------------------------------------------------------
# 1. Обработчик нажатия на кнопку «Согласен» (принятие правил)
# ----------------------------------------------------------------------
@router.callback(Registration.waiting_for_rules_consent)
async def process_rules_accept(event: MessageCallback, data: dict) -> None:
    """
    ✅ Обработчик нажатия кнопки «Согласен» после прочтения правил.

    Вызывается, когда пользователь находится в состоянии `waiting_for_rules_consent`
    и нажимает кнопку с callback_data = "accept_rules".

    Действия:
        - Извлекает пользователя из события.
        - Сохраняет в БД факт принятия правил с текущей датой.
        - Отвечает на callback (убирает "часики" на кнопке).
        - Убирает клавиатуру из исходного сообщения (чтобы кнопки не висели).
        - Отправляет новое сообщение с просьбой поделиться контактом.
        - Переводит пользователя в состояние `waiting_for_contact`.

    Аргументы:
        event (MessageCallback): событие нажатия на callback-кнопку
        data (dict): словарь с данными от диспетчера. Содержит ключ 'context' для работы с FSM
    """
    # Проверяем, что нажата именно нужная кнопка
    if event.callback.payload != "accept_rules":
        return

    # Получаем контекст FSM из data (он добавляется автоматически диспетчером)
    context: MemoryContext = data.get('context')
    if not context:
        logger.error("❌ Контекст не найден в данных обработчика")
        return

    user_id = event.from_user.id
    logger.info(f"👤 Пользователь {user_id} принял согласие с правилами")

    # Сохраняем согласие в базе данных
    await db.update_user(
        user_id,
        rules_accepted=True,
        rules_accepted_at=datetime.now(timezone.utc)
    )

    # Отвечаем на callback (уведомление появится на секунду)
    await event.answer("Спасибо! Правила приняты.")

    # Убираем клавиатуру из исходного сообщения (оставляем только текст)
    await event.message.edit_text(
        text=event.message.text,
        attachments=[]  # пустой список вложений удаляет клавиатуру
    )

    # Отправляем новое сообщение с кнопкой для отправки контакта
    await event.message.answer(
        text="✅ Отлично! Правила приняты. Теперь, чтобы подключиться к программе лояльности, "
             "нажми кнопку «📱 Поделиться контактом».",
        attachments=[get_contact_keyboard()]  # клавиатура передаётся как вложение
    )

    # Устанавливаем следующее состояние FSM
    await context.set_state(Registration.waiting_for_contact)


# ----------------------------------------------------------------------
# 2. Обработчик получения контакта (кнопка «Поделиться контактом»)
# ----------------------------------------------------------------------
@router.message_created(Registration.waiting_for_contact)
async def process_contact(event: MessageCreated, data: dict) -> None:
    """
    📞 Обработчик получения контакта от пользователя.

    Вызывается, когда пользователь находится в состоянии `waiting_for_contact`
    и отправляет сообщение с вложением типа `contact` (при нажатии на кнопку).

    Действия:
        - Проверяет наличие вложений и находит среди них контакт.
        - Логирует структуру вложения для отладки (чтобы точно знать, где лежит номер).
        - Извлекает номер телефона (пробует несколько вариантов).
        - Сохраняет номер в БД.
        - Переводит пользователя в состояние `waiting_for_first_name`.

    Аргументы:
        event (MessageCreated): событие создания сообщения
        data (dict): словарь с данными (содержит контекст FSM)
    """
    context: MemoryContext = data.get('context')
    if not context:
        logger.error("❌ Контекст не найден в данных обработчика")
        return

    # Если в сообщении нет вложений – напоминаем пользователю, что нужно нажать кнопку
    if not event.message.attachments:
        await event.message.answer(
            text="📱 Пожалуйста, нажмите кнопку «Поделиться контактом» на клавиатуре."
        )
        return

    # Ищем вложение типа "contact"
    contact_att = None
    for att in event.message.attachments:
        # Логируем каждое вложение – это поможет определить структуру
        logger.debug(f"📎 Вложение: type={att.type}, payload={att.payload}")
        if att.type == "contact":
            contact_att = att
            break

    if not contact_att:
        await event.message.answer(
            text="❌ Не удалось найти контакт. Пожалуйста, используйте кнопку."
        )
        return

    # Извлекаем номер телефона из вложения
    # В maxapi структура вложения может быть разной; пробуем несколько вариантов
    phone = None

    # Вариант 1: номер лежит в payload.phoneNumber (наиболее вероятно)
    if hasattr(contact_att, 'payload') and isinstance(contact_att.payload, dict):
        phone = contact_att.payload.get('phoneNumber')

    # Вариант 2: номер может быть прямым атрибутом (например, contact_att.phone)
    if not phone and hasattr(contact_att, 'phone'):
        phone = contact_att.phone

    # Вариант 3: номер может быть в поле id или token (маловероятно)
    if not phone and hasattr(contact_att, 'id'):
        phone = contact_att.id

    if not phone:
        logger.error(f"❌ Не удалось извлечь номер из контакта. Вложение: {contact_att}")
        await event.message.answer(
            text="❌ Не удалось получить номер телефона. Попробуйте ещё раз."
        )
        return

    # Приводим номер к формату с '+'
    if not phone.startswith('+'):
        phone = '+' + phone

    user_id = event.from_user.id
    await db.update_user(user_id, phone_number=phone)
    logger.info(f"✅ Пользователь {user_id} отправил контакт, номер сохранён: {phone}")

    # Подтверждаем получение и переходим к следующему шагу
    await event.message.answer(
        text="✅ Спасибо! Номер телефона сохранён.\n\n"
             "✍️ Теперь, пожалуйста, напишите ваше имя.",
        reply_markup=None  # убираем клавиатуру, если она была
    )
    await context.set_state(Registration.waiting_for_first_name)


# ----------------------------------------------------------------------
# 3. Обработчик ввода имени
# ----------------------------------------------------------------------
@router.message_created(Registration.waiting_for_first_name)
async def process_first_name(event: MessageCreated, data: dict) -> None:
    """
    ✍️ Обработчик ввода имени.

    Вызывается в состоянии `waiting_for_first_name`. Ожидает текстовое сообщение,
    проверяет, что оно не пустое и содержит только допустимые символы (буквы, пробелы, дефисы).
    Сохраняет очищенное имя в БД и переводит пользователя в состояние `waiting_for_last_name`.

    Аргументы:
        event (MessageCreated): событие создания сообщения
        data (dict): словарь с данными (контекст FSM)
    """
    context: MemoryContext = data.get('context')
    if not context:
        return

    # Проверяем, что сообщение содержит текст
    if not event.message.text:
        await event.message.answer(
            text="✍️ Пожалуйста, введите имя текстовым сообщением."
        )
        return

    user_id = event.from_user.id
    first_name_text = event.message.text.strip()
    logger.info(f"👤 Пользователь user_id={user_id} вводит имя: '{first_name_text}'")

    # Валидация имени
    is_valid, error_message = await validate_first_name(first_name_text)
    if not is_valid:
        await event.message.answer(text=error_message)
        return

    # Очистка от лишних пробелов
    first_name_cleaned = await clean_name(first_name_text)
    await db.update_user(user_id, first_name_input=first_name_cleaned)

    # Переходим к следующему шагу
    await event.message.answer(
        text="✅ Спасибо! Теперь напишите вашу фамилию."
    )
    await context.set_state(Registration.waiting_for_last_name)


# ----------------------------------------------------------------------
# 4. Обработчик ввода фамилии
# ----------------------------------------------------------------------
@router.message_created(Registration.waiting_for_last_name)
async def process_last_name(event: MessageCreated, data: dict) -> None:
    """
    👥 Обработчик ввода фамилии.

    Аналогичен `process_first_name`, но для фамилии. Сохраняет фамилию и переводит
    в состояние `waiting_for_gender` с показом клавиатуры выбора пола.

    Аргументы:
        event (MessageCreated): событие создания сообщения.
        data (dict): словарь с данными (контекст FSM).
    """
    context: MemoryContext = data.get('context')
    if not context:
        return

    if not event.message.text:
        await event.message.answer(
            text="✍️ Пожалуйста, введите фамилию текстовым сообщением."
        )
        return

    user_id = event.from_user.id
    last_name_text = event.message.text.strip()
    logger.info(f"👤 Пользователь user_id={user_id} вводит фамилию: '{last_name_text}'")

    is_valid, error_message = await validate_last_name(last_name_text)
    if not is_valid:
        await event.message.answer(text=error_message)
        return

    last_name_cleaned = await clean_name(last_name_text)
    await db.update_user(user_id, last_name_input=last_name_cleaned)

    # Отправляем сообщение с клавиатурой выбора пола
    await event.message.answer(
        text="👍 Отлично! Теперь укажите ваш пол:",
        attachments=[get_gender_keyboard()]
    )
    await context.set_state(Registration.waiting_for_gender)


# ----------------------------------------------------------------------
# 5. Обработчик выбора пола (callback)
# ----------------------------------------------------------------------
@router.callback(Registration.waiting_for_gender)
async def process_gender(event: MessageCallback, data: dict) -> None:
    """
    ⚥ Обработчик выбора пола.

    Реагирует на нажатие кнопок «Мужской» или «Женский». Сохраняет выбранный пол
    в БД, убирает клавиатуру и переводит пользователя в состояние `waiting_for_birth_date`
    с запросом даты рождения.

    Аргументы:
        event (MessageCallback): событие нажатия на callback-кнопку
        data (dict): словарь с данными (контекст FSM)
    """
    if event.callback.payload not in ["gender_male", "gender_female"]:
        return

    context: MemoryContext = data.get('context')
    if not context:
        return

    user_id = event.from_user.id
    gender_value = "male" if event.callback.payload == "gender_male" else "female"
    gender_text = "мужской" if gender_value == "male" else "женский"
    logger.info(f"👤 Пользователь user_id={user_id} выбрал пол: {gender_text}")

    await db.update_user(user_id, gender=gender_value)

    # Отвечаем на callback (убираем "часики")
    await event.answer("")

    # Убираем клавиатуру из текущего сообщения
    await event.message.edit_text(
        text=event.message.text,
        attachments=[]
    )

    # Отправляем запрос даты рождения
    await event.message.answer(
        text="✅ Спасибо! Теперь укажите вашу дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990)."
    )
    await context.set_state(Registration.waiting_for_birth_date)


# ----------------------------------------------------------------------
# 6. Обработчик ввода даты рождения
# ----------------------------------------------------------------------
@router.message_created(Registration.waiting_for_birth_date)
async def process_birth_date(event: MessageCreated, data: dict) -> None:
    """
    🎂 Обработчик ввода даты рождения.

    Проверяет формат (ДД.ММ.ГГГГ), корректность даты, возраст (от 18 до 100 лет).
    Сохраняет дату и переводит в состояние `waiting_for_email`.

    Аргументы:
        event (MessageCreated): событие создания сообщения
        data (dict): словарь с данными (контекст FSM)
    """
    context: MemoryContext = data.get('context')
    if not context:
        return

    if not event.message.text:
        await event.message.answer(
            text="✍️ Пожалуйста, введите дату текстовым сообщением."
        )
        return

    user_id = event.from_user.id
    text = event.message.text.strip()
    logger.info(f"👤 Пользователь user_id={user_id} вводит дату рождения: '{text}'")

    is_valid, error_message = await validate_birth_date(text)
    if not is_valid:
        await event.message.answer(text=error_message)
        return

    # Преобразуем строку в объект date
    from datetime import datetime
    birth = datetime.strptime(text, "%d.%m.%Y").date()
    await db.update_user(user_id, birth_date=birth)

    await event.message.answer(
        text="✅ Спасибо! Дата рождения сохранена.\n\n"
             "📧 Теперь, пожалуйста, укажите ваш адрес электронной почты."
    )
    await context.set_state(Registration.waiting_for_email)


# ----------------------------------------------------------------------
# 7. Обработчик ввода email
# ----------------------------------------------------------------------
@router.message_created(Registration.waiting_for_email)
async def process_email(event: MessageCreated, data: dict) -> None:
    """
    📧 Обработчик ввода email.

    Проверяет корректность формата email, сохраняет его и переходит к показу анкеты
    для подтверждения (вызов `show_profile_review`).

    Аргументы:
        event (MessageCreated): событие создания сообщения.
        data (dict): словарь с данными (контекст FSM).
    """
    context: MemoryContext = data.get('context')
    if not context:
        return

    if not event.message.text:
        await event.message.answer(
            text="✍️ Пожалуйста, введите почту текстовым сообщением."
        )
        return

    user_id = event.from_user.id
    email = event.message.text.strip()
    logger.info(f"👤 Пользователь user_id={user_id} вводит email: '{email}'")

    is_valid, error_message = await validate_email(email)
    if not is_valid:
        await event.message.answer(text=error_message)
        return

    await db.update_user(user_id, email=email)

    # Показываем анкету для подтверждения
    # Функция show_profile_review должна быть адаптирована под maxapi и принимать event, context и целевое состояние
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


# ----------------------------------------------------------------------
# 8. Обработчики ревью анкеты (кнопки «Всё верно» / «Изменить»)
# ----------------------------------------------------------------------
@router.callback(Registration.waiting_for_review)
async def process_review(event: MessageCallback, data: dict) -> None:
    """
    📋 Обработчик нажатия кнопок на этапе подтверждения анкеты.

    - Если нажата кнопка «✅ Всё верно» (payload="review_correct"): переходит к согласию на уведомления.
    - Если нажата кнопка «✏️ Изменить» (payload="review_edit"): показывает меню выбора поля для редактирования.

    Аргументы:
        event (MessageCallback): событие нажатия на callback-кнопку
        data (dict): словарь с данными (контекст FSM)
    """
    context: MemoryContext = data.get('context')
    if not context:
        return

    if event.callback.payload == "review_correct":
        # Подтверждение анкеты
        await event.answer("")
        # Убираем клавиатуру из текущего сообщения
        await event.message.edit_text(
            text=event.message.text,
            attachments=[]
        )
        # Отправляем сообщение с клавиатурой для согласия на уведомления
        await event.message.answer(
            text="📢 Мы хотим радовать вас уникальными предложениями и акциями.\n"
                 "Ознакомьтесь с условиями получения уведомлений по ссылке ниже и сделайте выбор:",
            attachments=[get_notifications_keyboard()]
        )
        await context.set_state(Registration.waiting_for_notifications_consent)

    elif event.callback.payload == "review_edit":
        # Редактирование анкеты – показываем меню выбора поля
        await event.answer("")
        text = "🔧 Выберите, что хотите исправить:"
        await event.message.edit_text(
            text=text,
            attachments=[get_edit_choice_keyboard()]
        )
        await context.set_state(Registration.waiting_for_edit_choice)


# ----------------------------------------------------------------------
# 9. Обработчик выбора поля для редактирования (меню)
# ----------------------------------------------------------------------
@router.callback(Registration.waiting_for_edit_choice)
async def process_edit_choice(event: MessageCallback, data: dict) -> None:
    """
    🔧 Обработчик выбора конкретного поля для редактирования.

    В зависимости от payload (edit_first_name, edit_last_name и т.д.) устанавливает
    соответствующее состояние (waiting_for_edit_имя) и отправляет запрос на ввод нового значения.

    Для поля «Пол» сразу показывает клавиатуру выбора.

    Аргументы:
        event (MessageCallback): событие нажатия на callback-кнопку.
        data (dict): словарь с данными (контекст FSM).
    """
    context: MemoryContext = data.get('context')
    if not context:
        return

    payload = event.callback.payload
    await event.answer("")

    # Если пользователь нажал «Отмена» – возвращаемся к анкете
    if payload == "edit_cancel":
        await show_profile_review(event, context, target_state=Registration.waiting_for_review)
        return

    # Словарь, связывающий payload с состоянием, текстом запроса и клавиатурой (если есть)
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
        # Отправляем запрос (с клавиатурой, если есть)
        await event.message.edit_text(
            text=text,
            attachments=[keyboard] if keyboard else []
        )
        await context.set_state(new_state)
    else:
        # Неизвестный payload – на всякий случай возвращаем к анкете
        await show_profile_review(event, context, target_state=Registration.waiting_for_review)


# ----------------------------------------------------------------------
# 10. Обработчики редактирования каждого поля (текстовые)
# ----------------------------------------------------------------------
@router.message_created(Registration.waiting_for_edit_first_name)
async def process_edit_first_name(event: MessageCreated, data: dict) -> None:
    """
    ✏️ Обработчик редактирования имени.

    Проверяет новое имя, сохраняет его и возвращается к анкете.
    """
    context: MemoryContext = data.get('context')
    if not context:
        return

    if not event.message.text:
        await event.message.answer(text="✍️ Пожалуйста, введите имя текстовым сообщением.")
        return

    user_id = event.from_user.id
    value = event.message.text.strip()
    is_valid, error = await validate_first_name(value)
    if not is_valid:
        await event.message.answer(text=error)
        return

    cleaned = await clean_name(value)
    await db.update_user(user_id, first_name_input=cleaned)
    # Возвращаемся к анкете
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.message_created(Registration.waiting_for_edit_last_name)
async def process_edit_last_name(event: MessageCreated, data: dict) -> None:
    """
    ✏️ Обработчик редактирования фамилии.
    """
    context: MemoryContext = data.get('context')
    if not context:
        return

    if not event.message.text:
        await event.message.answer(text="✍️ Пожалуйста, введите фамилию текстовым сообщением.")
        return

    user_id = event.from_user.id
    value = event.message.text.strip()
    is_valid, error = await validate_last_name(value)
    if not is_valid:
        await event.message.answer(text=error)
        return

    cleaned = await clean_name(value)
    await db.update_user(user_id, last_name_input=cleaned)
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.callback(Registration.waiting_for_edit_gender)
async def process_edit_gender(event: MessageCallback, data: dict) -> None:
    """
    ✏️ Обработчик редактирования пола (callback).
    """
    if event.callback.payload not in ["gender_male", "gender_female"]:
        return

    context: MemoryContext = data.get('context')
    if not context:
        return

    user_id = event.from_user.id
    gender = "male" if event.callback.payload == "gender_male" else "female"
    await db.update_user(user_id, gender=gender)
    await event.answer("✅ Пол сохранён.")
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.message_created(Registration.waiting_for_edit_birth_date)
async def process_edit_birth_date(event: MessageCreated, data: dict) -> None:
    """
    ✏️ Обработчик редактирования даты рождения.
    """
    context: MemoryContext = data.get('context')
    if not context:
        return

    if not event.message.text:
        await event.message.answer(text="✍️ Пожалуйста, введите дату текстовым сообщением.")
        return

    user_id = event.from_user.id
    value = event.message.text.strip()
    is_valid, error = await validate_birth_date(value)
    if not is_valid:
        await event.message.answer(text=error)
        return

    from datetime import datetime
    birth = datetime.strptime(value, "%d.%m.%Y").date()
    await db.update_user(user_id, birth_date=birth)
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


@router.message_created(Registration.waiting_for_edit_email)
async def process_edit_email(event: MessageCreated, data: dict) -> None:
    """
    ✏️ Обработчик редактирования email.
    """
    context: MemoryContext = data.get('context')
    if not context:
        return

    if not event.message.text:
        await event.message.answer(text="✍️ Пожалуйста, введите почту текстовым сообщением.")
        return

    user_id = event.from_user.id
    value = event.message.text.strip()
    is_valid, error = await validate_email(value)
    if not is_valid:
        await event.message.answer(text=error)
        return

    await db.update_user(user_id, email=value)
    await show_profile_review(event, context, target_state=Registration.waiting_for_review)


# ----------------------------------------------------------------------
# 11. Обработчик согласия на уведомления
# ----------------------------------------------------------------------
@router.callback(Registration.waiting_for_notifications_consent)
async def process_notifications_consent(event: MessageCallback, data: dict) -> None:
    """
    🔔 Обработчик выбора пользователя по согласию на уведомления.

    Кнопки: «✅ О да, кидай всё, что есть!» (notify_yes) и «❌ Нет» (notify_no).
    Сохраняет выбор, снимает флаг is_legacy (если был), переводит в состояние ожидания iiko
    и запускает синхронизацию с iiko.

    Аргументы:
        event (MessageCallback): событие нажатия на callback-кнопку.
        data (dict): словарь с данными (контекст FSM).
    """
    if event.callback.payload not in ["notify_yes", "notify_no"]:
        return

    context: MemoryContext = data.get('context')
    if not context:
        return

    user_id = event.from_user.id
    notifications_allowed = (event.callback.payload == "notify_yes")
    choice_text = "согласился на уведомления" if notifications_allowed else "отказался от уведомлений"
    logger.info(f"👤 Пользователь user_id={user_id} {choice_text}")

    # Обновляем запись в БД
    await db.update_user(
        user_id,
        notifications_allowed=notifications_allowed,
        notifications_allowed_at=datetime.now(timezone.utc),
        # Если пользователь был legacy, снимаем этот флаг
        is_legacy=False
    )

    await event.answer("")
    # Убираем клавиатуру из текущего сообщения
    await event.message.edit_text(
        text=event.message.text,
        attachments=[]
    )

    # Получаем обновлённого пользователя
    user = await db.get_user(user_id)
    if not user:
        await event.message.answer(text="❌ Ошибка загрузки пользователя")
        await context.clear()
        return

    # Переходим в состояние ожидания iiko и запускаем синхронизацию
    await context.set_state(Registration.waiting_for_iiko_registration)
    await sync_user_with_iiko(event, user)


# ----------------------------------------------------------------------
# 12. Обработчик повторной попытки регистрации в iiko (кнопка retry)
# ----------------------------------------------------------------------
@router.callback(Registration.waiting_for_iiko_registration)
async def retry_iiko_registration(event: MessageCallback, data: dict) -> None:
    """
    🔄 Повторная попытка синхронизации с iiko при ошибке.

    Вызывается при нажатии на кнопку «🔄 Повторить попытку» (payload="retry_iiko_registration").
    Загружает пользователя и снова запускает sync_user_with_iiko.

    Аргументы:
        event (MessageCallback): событие нажатия на callback-кнопку.
        data (dict): словарь с данными (контекст FSM).
    """
    if event.callback.payload != "retry_iiko_registration":
        return

    context: MemoryContext = data.get('context')
    if not context:
        return

    await event.answer("")
    user = await db.get_user(event.from_user.id)
    if not user:
        await event.message.answer(text="❌ Ошибка загрузки пользователя")
        await context.clear()
        return

    await sync_user_with_iiko(event, user)
