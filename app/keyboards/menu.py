"""
Клавиатуры для главного меню и подменю.
=========================================
Содержит функции для создания:
- главного меню (баланс, карта, отдел заботы, вакансии)
- подменю отдела заботы
- кнопок возврата

Все клавиатуры создаются с помощью InlineKeyboardBuilder из maxapi.
"""

from maxapi.types import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard():
    """
    Главное меню бота.

    Содержит четыре кнопки:
    - «💰 Мой баланс» – просмотр бонусного баланса.
    - «🪪 Виртуальная карта» – показать карты и QR-коды.
    - «🆘 Отдел заботы» – переход во вложенное меню поддержки.
    - «💼 Вакансии» – информация о вакансиях.

    Каждая кнопка при нажатии отправляет callback с соответствующим payload.

    Returns:
        InlineKeyboardMarkup: готовая клавиатура (объект вложения).
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        CallbackButton(text="💰 Мой баланс", payload="balance")
    )
    builder.row(
        CallbackButton(text="🪪 Виртуальная карта", payload="virtual_card")
    )
    builder.row(
        CallbackButton(text="🆘 Отдел заботы", payload="support")
    )
    builder.row(
        CallbackButton(text="💼 Вакансии", payload="vacancies")
    )

    return builder.as_markup()


def get_support_submenu_keyboard(has_tickets: bool = False):
    """
    Подменю отдела заботы.

    В зависимости от наличия тикетов у пользователя может показывать
    дополнительную кнопку «Мои обращения».

    Args:
        has_tickets (bool): есть ли у пользователя открытые тикеты.

    Кнопки:
    - «✍️ Оставить отзыв» – переход к внешней форме.
    - «❓ Мне только спросить» – создание нового тикета.
    - «📋 Мои обращения» – просмотр списка тикетов (если has_tickets=True).
    - «📧 Контакты» – контактная информация.
    - «🔙 Назад в меню» – возврат в главное меню.

    Returns:
        InlineKeyboardMarkup: клавиатура.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        CallbackButton(text="✍️ Оставить отзыв", payload="support_feedback")
    )
    builder.row(
        CallbackButton(text="❓ Мне только спросить", payload="support_question")
    )

    if has_tickets:
        builder.row(
            CallbackButton(text="📋 Мои обращения", payload="my_tickets")
        )

    builder.row(
        CallbackButton(text="📧 Контакты", payload="support_contacts")
    )
    builder.row(
        CallbackButton(text="🔙 Назад в меню", payload="back_to_main")
    )

    return builder.as_markup()


def get_back_to_main_keyboard():
    """
    Кнопка возврата в главное меню.

    Используется в разделах, где нет собственного подменю.

    Returns:
        InlineKeyboardMarkup: клавиатура с одной кнопкой.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="🔙 Назад в меню", payload="back_to_main")
    )
    return builder.as_markup()


def get_back_to_support_keyboard():
    """
    Кнопка возврата в отдел заботы.

    Используется внутри разделов отдела заботы (отзыв, вопрос, контакты).

    Returns:
        InlineKeyboardMarkup: клавиатура с одной кнопкой.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="🔙 Назад в отдел заботы", payload="back_to_support")
    )
    return builder.as_markup()
