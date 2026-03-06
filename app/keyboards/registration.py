"""
Клавиатуры для процесса регистрации.
======================================
Содержат функции, возвращающие готовые объекты клавиатур для различных шагов регистрации:
- согласие с правилами
- запрос контакта
- выбор пола
- согласие на уведомления
- подтверждение анкеты
- выбор поля для редактирования.
"""

# Импортируем необходимые типы кнопок из maxapi
from maxapi.types import (
    LinkButton,            # кнопка-ссылка
    CallbackButton,        # кнопка с callback-данными
    RequestContactButton,  # кнопка запроса контакта
)

# Импортируем строитель клавиатур
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


def get_rules_keyboard():
    """
    📜 Клавиатура для принятия правил.

    Содержит:
    - кнопку-ссылку на документы с правилами
    - кнопку «Согласен» с callback-данными

    Возвращает:
        InlineKeyboardMarkup: готовая клавиатура для отправки.
    """
    builder = InlineKeyboardBuilder()

    # Кнопка-ссылка на страницу с документами
    builder.row(
        LinkButton(
            text="📄 Открыть документы",
            url="https://sagur.24vds.ru/agreement/"
        )
    )

    # Кнопка для подтверждения согласия
    builder.row(
        CallbackButton(
            text="✅ Согласен",
            payload="accept_rules"  # эти данные придут в событии MessageCallback
        )
    )

    # Возвращаем готовую клавиатуру (это объект Attachment, который нужно поместить в attachments сообщения)
    return builder.as_markup()


def get_contact_keyboard():
    """
    📱 Клавиатура для запроса контакта.

    Содержит одну кнопку «Поделиться контактом» специального типа.
    При нажатии пользователь отправляет свой номер телефона (в MAX это работает как вложение).

    Возвращает:
        InlineKeyboardMarkup: клавиатура с кнопкой запроса контакта.
    """
    builder = InlineKeyboardBuilder()

    # Кнопка запроса контакта (специальный тип, не требует payload/url)
    builder.row(
        RequestContactButton(
            text="📱 Поделиться контактом"
        )
    )

    return builder.as_markup()


def get_gender_keyboard():
    """
    ⚥ Клавиатура для выбора пола.

    Содержит две кнопки: «Мужской» и «Женский» с соответствующими callback-данными.

    Возвращает:
        InlineKeyboardMarkup: клавиатура с двумя кнопками в одном ряду.
    """
    builder = InlineKeyboardBuilder()

    # Добавляем две кнопки в один ряд
    builder.row(
        CallbackButton(text="Мужской", payload="gender_male"),
        CallbackButton(text="Женский", payload="gender_female")
    )

    return builder.as_markup()


def get_notifications_keyboard():
    """
    🔔 Клавиатура для согласия на уведомления.

    Содержит:
    - кнопку-ссылку на условия получения уведомлений
    - кнопку «Да» с callback-данными
    - кнопку «Нет» с callback-данными

    Возвращает:
        InlineKeyboardMarkup: клавиатура для выбора.
    """
    builder = InlineKeyboardBuilder()

    # Кнопка-ссылка на условия
    builder.row(
        LinkButton(
            text="📄 Условия получения уведомлений",
            url="https://sagur.24vds.ru/notifications/"
        )
    )

    # Кнопка «Да»
    builder.row(
        CallbackButton(
            text="✅ О да, кидай всё, что есть! 🔥",
            payload="notify_yes"
        )
    )

    # Кнопка «Нет»
    builder.row(
        CallbackButton(
            text="❌ Нет, останусь без подарков… 🙁",
            payload="notify_no"
        )
    )

    return builder.as_markup()


def get_review_keyboard():
    """
    📋 Клавиатура для подтверждения анкеты.

    Содержит кнопки «Всё верно» и «Изменить» с соответствующими callback-данными.

    Возвращает:
        InlineKeyboardMarkup: клавиатура для подтверждения.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        CallbackButton(text="✅ Всё верно", payload="review_correct")
    )
    builder.row(
        CallbackButton(text="✏️ Изменить", payload="review_edit")
    )

    return builder.as_markup()


def get_edit_choice_keyboard():
    """
    ✏️ Клавиатура для выбора редактируемого поля.

    Содержит кнопки для каждого поля (имя, фамилия, пол, дата рождения, email)
    и кнопку отмены. Все кнопки отправляют соответствующие callback-данные.

    Возвращает:
        InlineKeyboardMarkup: клавиатура для выбора поля.
    """
    builder = InlineKeyboardBuilder()

    fields = [
        ("👤 Имя", "edit_first_name"),
        ("👥 Фамилия", "edit_last_name"),
        ("⚥ Пол", "edit_gender"),
        ("🎂 Дата рождения", "edit_birth_date"),
        ("📧 Email", "edit_email"),
    ]

    for text, callback in fields:
        builder.row(
            CallbackButton(text=text, payload=callback)
        )

    # Кнопка отмены
    builder.row(
        CallbackButton(text="🔙 Отмена", payload="edit_cancel")
    )

    return builder.as_markup()
