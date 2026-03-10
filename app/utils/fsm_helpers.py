"""
Вспомогательные функции для работы с FSM.
"""

from typing import Optional, Tuple, Any

from maxapi.context import State
from maxapi.types import MessageCreated
from loguru import logger

from app.keyboards.registration import (
    get_rules_keyboard,
    get_contact_keyboard,
    get_gender_keyboard,
    get_notifications_keyboard,
    get_edit_choice_keyboard,
    get_review_keyboard,
)
from app.states.registration import Registration
from app.states.legacy import LegacyUpgrade
from app.states.admin import AdminStates
from app.states.tickets import TicketStates, UserTicketStates
from app.utils.profile import show_profile_review


def get_prompt_for_state(state: State, context: Any) -> Tuple[str, Optional[Any]]:
    """
    Возвращает текст и клавиатуру для заданного состояния.
    Для состояний, требующих дополнительных данных, извлекает их из контекста.
    """
    # ------------------ Registration ------------------
    if state == Registration.waiting_for_rules_consent:
        return (
            "📜 Для начала нам необходимо получить твоё согласие на обработку персональных данных "
            "и согласие с политикой конфиденциальности.\n\n"
            "👉 Ознакомься с документами по ссылке ниже и нажми «✅ Согласен».",
            get_rules_keyboard()
        )
    if state == Registration.waiting_for_contact:
        return (
            "📱 Чтобы подключиться к программе лояльности, нажми кнопку «Поделиться контактом».",
            get_contact_keyboard()
        )
    if state == Registration.waiting_for_first_name:
        return ("✍️ Введите ваше имя:", None)
    if state == Registration.waiting_for_last_name:
        return ("✍️ Введите вашу фамилию:", None)
    if state == Registration.waiting_for_gender:
        return ("Выберите ваш пол:", get_gender_keyboard())
    if state == Registration.waiting_for_birth_date:
        return ("📅 Введите вашу дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990):", None)
    if state == Registration.waiting_for_email:
        return ("📧 Введите ваш email:", None)
    if state == Registration.waiting_for_review:
        # Для этого состояния используем show_profile_review, поэтому возвращаем специальный маркер
        return ("__SHOW_PROFILE_REVIEW__", None)
    if state == Registration.waiting_for_edit_choice:
        return ("🔧 Выберите, что хотите исправить:", get_edit_choice_keyboard())
    if state == Registration.waiting_for_notifications_consent:
        return (
            "📢 Мы хотим радовать вас уникальными предложениями и акциями.\n"
            "Ознакомьтесь с условиями получения уведомлений по ссылке ниже и сделайте выбор:",
            get_notifications_keyboard()
        )
    if state == Registration.waiting_for_iiko_registration:
        return ("⏳ Идёт регистрация в бонусной системе...", None)

    # ------------------ Legacy Upgrade ------------------
    if state == LegacyUpgrade.waiting_for_rules_consent:
        return (
            "📜 Для начала нам необходимо получить твоё согласие на обработку персональных данных "
            "и согласие с политикой конфиденциальности.\n\n"
            "👉 Ознакомься с документами по ссылке ниже и нажми «✅ Согласен».",
            get_rules_keyboard()
        )
    if state == LegacyUpgrade.waiting_for_field:
        # Нужно определить, какое поле ожидается
        data = context.get_data()  # предполагаем, что context имеет метод get_data
        missing = data.get('missing_fields', [])
        if missing:
            field = missing[0]
            if field == 'first_name':
                return ("✍️ Введите ваше имя:", None)
            if field == 'last_name':
                return ("✍️ Введите вашу фамилию:", None)
            if field == 'gender':
                return ("Выберите ваш пол:", get_gender_keyboard())
            if field == 'birth_date':
                return ("📅 Введите вашу дату рождения (ДД.ММ.ГГГГ):", None)
            if field == 'email':
                return ("📧 Введите ваш email:", None)
        return ("👋 Пожалуйста, продолжите заполнение данных.", None)
    if state == LegacyUpgrade.waiting_for_review:
        return ("__SHOW_PROFILE_REVIEW__", None)
    if state == LegacyUpgrade.waiting_for_edit_choice:
        return ("🔧 Выберите, что хотите исправить:", get_edit_choice_keyboard())
    if state == LegacyUpgrade.waiting_for_edit_field:
        # Аналогично waiting_for_field, нужно знать, какое поле редактируется
        data = context.get_data()
        field = data.get('edit_field')
        if field == 'edit_first_name':
            return ("✍️ Введите новое имя:", None)
        if field == 'edit_last_name':
            return ("✍️ Введите новую фамилию:", None)
        if field == 'edit_gender':
            return ("Выберите ваш пол:", get_gender_keyboard())
        if field == 'edit_birth_date':
            return ("📅 Введите новую дату рождения (ДД.ММ.ГГГГ):", None)
        if field == 'edit_email':
            return ("📧 Введите новый email:", None)
        return ("📝 Введите новое значение:", None)
    if state == LegacyUpgrade.waiting_for_notifications_consent:
        return (
            "📢 Мы хотим радовать вас уникальными предложениями и акциями.\n"
            "Ознакомьтесь с условиями получения уведомлений по ссылке ниже и сделайте выбор:",
            get_notifications_keyboard()
        )
    if state == LegacyUpgrade.waiting_for_iiko_registration:
        return ("⏳ Идёт регистрация в бонусной системе...", None)

    # ------------------ Прочие состояния (можно добавить при необходимости) ------------------
    return ("👋 Продолжите работу, следуя инструкциям.", None)
