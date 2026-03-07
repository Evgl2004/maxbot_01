"""
Клавиатуры для процесса регистрации.
======================================
Содержит функции, возвращающие готовые объекты клавиатур для различных шагов регистрации:
- согласие с правилами
- запрос контакта
- выбор пола
- согласие на уведомления
- подтверждение анкеты
- выбор поля для редактирования

Все клавиатуры создаются с помощью InlineKeyboardBuilder из maxapi.
"""

from maxapi.types import CallbackButton, LinkButton, RequestContactButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


def get_rules_keyboard():
    """
    Клавиатура для принятия правил.

    Содержит кнопку-ссылку на документы и кнопку «Согласен» с callback-данными.

    Returns:
        InlineKeyboardMarkup: готовая клавиатура (объект вложения).
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        LinkButton(text="📄 Открыть документы", url="https://sagur.24vds.ru/agreement/")
    )
    builder.row(
        CallbackButton(text="✅ Согласен", payload="accept_rules")
    )
    return builder.as_markup()


def get_contact_keyboard():
    """
    Клавиатура для запроса контакта.

    Содержит одну кнопку «Поделиться контактом» специального типа RequestContactButton.
    При нажатии пользователь отправляет свой номер телефона как вложение типа contact.

    Returns:
        InlineKeyboardMarkup: клавиатура с кнопкой запроса контакта.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        RequestContactButton(text="📱 Поделиться контактом")
    )
    return builder.as_markup()


def get_gender_keyboard():
    """
    Клавиатура для выбора пола.

    Содержит две кнопки: «Мужской» и «Женский» с соответствующими callback-данными.

    Returns:
        InlineKeyboardMarkup: клавиатура с двумя кнопками в одном ряду.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Мужской", payload="gender_male"),
        CallbackButton(text="Женский", payload="gender_female")
    )
    return builder.as_markup()


def get_notifications_keyboard():
    """
    Клавиатура для согласия на уведомления.

    Содержит кнопку-ссылку на условия, кнопку «Да» и кнопку «Нет».

    Returns:
        InlineKeyboardMarkup: клавиатура для выбора.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        LinkButton(text="📄 Условия получения уведомлений", url="https://sagur.24vds.ru/notifications/")
    )
    builder.row(
        CallbackButton(text="✅ О да, кидай всё, что есть! 🔥", payload="notify_yes")
    )
    builder.row(
        CallbackButton(text="❌ Нет, останусь без подарков… 🙁", payload="notify_no")
    )
    return builder.as_markup()


def get_review_keyboard():
    """
    Клавиатура для подтверждения анкеты.

    Содержит кнопки «Всё верно» и «Изменить» с соответствующими callback-данными.

    Returns:
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
    Клавиатура для выбора редактируемого поля.

    Содержит кнопки для каждого поля (имя, фамилия, пол, дата рождения, email)
    и кнопку отмены. Все кнопки отправляют соответствующие callback-данные.

    Returns:
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
        builder.row(CallbackButton(text=text, payload=callback))
    builder.row(CallbackButton(text="🔙 Отмена", payload="edit_cancel"))
    return builder.as_markup()
