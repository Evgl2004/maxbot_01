"""
Клавиатуры для процесса регистрации.
"""

from maxbot.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_rules_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой-ссылкой на документы и кнопкой «Согласен».
    """
    keyboard = [
        [InlineKeyboardButton(text="📄 Открыть документы", url="https://sagur.24vds.ru/agreement/")],
        [InlineKeyboardButton(text="✅ Согласен", callback_data="accept_rules")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_contact_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой для отправки контакта (inline-кнопка с type='request_contact').
    """
    keyboard = [[
        InlineKeyboardButton(
            text="📱 Поделиться контактом",
            type="request_contact"  # специальный тип для запроса контакта
        )
    ]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора пола."""
    keyboard = [[
        InlineKeyboardButton(text="Мужской", callback_data="gender_male"),
        InlineKeyboardButton(text="Женский", callback_data="gender_female")
    ]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_notifications_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для согласия на уведомления."""
    keyboard = [
        [InlineKeyboardButton(text="📄 Условия получения уведомлений",
                               url="https://sagur.24vds.ru/notifications/")],
        [InlineKeyboardButton(text="✅ О да, кидай всё, что есть! 🔥",
                               callback_data="notify_yes")],
        [InlineKeyboardButton(text="❌ Нет, останусь без подарков… 🙁",
                               callback_data="notify_no")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_review_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения анкеты."""
    keyboard = [
        [InlineKeyboardButton(text="✅ Всё верно", callback_data="review_correct")],
        [InlineKeyboardButton(text="✏️ Изменить", callback_data="review_edit")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_edit_choice_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора редактируемого поля."""
    keyboard = [
        [InlineKeyboardButton(text="👤 Имя", callback_data="edit_first_name")],
        [InlineKeyboardButton(text="👥 Фамилия", callback_data="edit_last_name")],
        [InlineKeyboardButton(text="⚥ Пол", callback_data="edit_gender")],
        [InlineKeyboardButton(text="🎂 Дата рождения", callback_data="edit_birth_date")],
        [InlineKeyboardButton(text="📧 Email", callback_data="edit_email")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="edit_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
