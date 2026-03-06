"""
Клавиатуры для админской части
================================
Содержат кнопки для главного меню администратора,
подтверждения рассылки, добавления кнопок, настроек API и др.
Все кнопки используют типы из maxapi: CallbackButton, LinkButton.
"""

from maxapi.types import CallbackButton, LinkButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

# Импорт настроек (используется для определения текущего режима API)
from app.config import settings


class AdminKeyboards:
    """
    📋 Набор статических методов для создания админских клавиатур.
    """

    @staticmethod
    def main_admin_menu():
        """
        🏠 Главное меню администратора.

        Содержит три кнопки:
        - 📊 Рассылка – переход к созданию рассылки.
        - 👨‍💼 Модератор – открывает меню модерации (отдельный раздел).
        - ⚙️ Настройки API – просмотр и изменение режима API (Local/Public).

        Возвращает:
            InlineKeyboardMarkup (attachment): готовая клавиатура.
        """
        builder = InlineKeyboardBuilder()

        builder.row(
            CallbackButton(text="📊 Рассылка", payload="admin_broadcast")
        )
        builder.row(
            CallbackButton(text="👨‍💼 Модератор", payload="mod_main")
        )
        builder.row(
            CallbackButton(text="⚙️ Настройки API", payload="admin_api_settings")
        )

        return builder.as_markup()

    @staticmethod
    def broadcast_confirm(message_count: int):
        """
        ✅ Подтверждение рассылки.

        Показывает количество получателей и предлагает подтвердить или отменить.

        Аргументы:
            message_count (int): число пользователей, которым будет отправлена рассылка.

        Кнопки:
        - «✅ Отправить (X польз.)» – запуск рассылки.
        - «❌ Отменить» – возврат в меню.

        Возвращает:
            InlineKeyboardMarkup.
        """
        builder = InlineKeyboardBuilder()

        builder.row(
            CallbackButton(
                text=f"✅ Отправить ({message_count} польз.)",
                payload="broadcast_confirm_yes"
            )
        )
        builder.row(
            CallbackButton(text="❌ Отменить", payload="broadcast_confirm_no")
        )

        return builder.as_markup()

    @staticmethod
    def broadcast_add_button():
        """
        ➕ Меню добавления кнопки к рассылке.

        Предлагает три варианта:
        - Добавить кнопку (переход к вводу).
        - Отправить без кнопки.
        - Отменить создание рассылки.

        Возвращает:
            InlineKeyboardMarkup.
        """
        builder = InlineKeyboardBuilder()

        builder.row(
            CallbackButton(text="➕ Добавить кнопку", payload="broadcast_add_button")
        )
        builder.row(
            CallbackButton(text="📤 Отправить без кнопки", payload="broadcast_no_button")
        )
        builder.row(
            CallbackButton(text="❌ Отменить", payload="broadcast_cancel")
        )

        return builder.as_markup()

    @staticmethod
    def broadcast_button_confirm():
        """
        ✅ Подтверждение кнопки для рассылки.

        После ввода текста и URL кнопки администратору показывается
        предварительный просмотр и предлагается подтвердить или отменить.

        Кнопки:
        - «✅ Подтвердить» – завершить создание и перейти к отправке.
        - «❌ Отменить» – вернуться в меню.

        Возвращает:
            InlineKeyboardMarkup.
        """
        builder = InlineKeyboardBuilder()

        builder.row(
            CallbackButton(text="✅ Подтвердить", payload="broadcast_button_confirm")
        )
        builder.row(
            CallbackButton(text="❌ Отменить", payload="broadcast_cancel")
        )

        return builder.as_markup()

    @staticmethod
    def create_custom_button(text: str, url: str):
        """
        🔗 Создание кнопки-ссылки для предварительного просмотра.

        Используется для демонстрации того, как будет выглядеть кнопка в сообщении.
        Кнопка будет типа link, ведущая на указанный URL.

        Аргументы:
            text (str): текст кнопки.
            url (str): ссылка.

        Возвращает:
            InlineKeyboardMarkup с одной кнопкой-ссылкой.
        """
        builder = InlineKeyboardBuilder()

        builder.row(
            LinkButton(text=text, url=url)
        )

        return builder.as_markup()

    @staticmethod
    def api_settings_menu(is_local_mode: bool):
        """
        ⚙️ Меню настроек API (Telegram Local Bot API – для справки).

        В оригинале здесь были кнопки переключения между Local и Public API,
        проверки статуса и возврата. В MAX этот функционал неактуален,
        но оставлен для совместимости, чтобы не ломать логику навигации.

        Аргументы:
            is_local_mode (bool): флаг, включён ли Local Bot API (из settings).

        Кнопки:
        - Переключение режима (текст зависит от is_local_mode).
        - Проверка статуса.
        - Назад.

        Возвращает:
            InlineKeyboardMarkup.
        """
        builder = InlineKeyboardBuilder()

        # Формируем текст в зависимости от текущего режима
        switch_text = "🌍 Перейти на Public API" if is_local_mode else "🟢 Перейти на Local API"

        builder.row(
            CallbackButton(text=switch_text, payload="api_switch_mode")
        )
        builder.row(
            CallbackButton(text="📊 Проверить статус", payload="api_check_status")
        )
        builder.row(
            CallbackButton(text="◀️ Назад", payload="api_back")
        )

        return builder.as_markup()

    @staticmethod
    def api_settings_back():
        """
        🔙 Кнопка возврата из инструкций API.

        Используется после отображения инструкции по переключению режима,
        чтобы вернуться к меню настроек.

        Возвращает:
            InlineKeyboardMarkup с одной кнопкой.
        """
        builder = InlineKeyboardBuilder()

        builder.row(
            CallbackButton(text="◀️ Назад к настройкам", payload="admin_api_settings")
        )

        return builder.as_markup()
