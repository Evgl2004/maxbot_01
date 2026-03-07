"""Общие функции валидации данных пользователей."""

import re
from datetime import datetime, date
from typing import Tuple

from maxapi.types import MessageCreated


async def validate_first_name(value: str) -> Tuple[bool, str]:
    """
    Проверяет корректность введённого имени.

    Имя не должно быть пустым и должно содержать только буквы (русские/латиница),
    пробелы и дефисы.

    Args:
        value (str): введённое пользователем имя.

    Returns:
        Tuple[bool, str]: (True, "") если валидация пройдена,
                           (False, сообщение_об_ошибке) в противном случае.
    """
    if not value:
        return False, "❌ Имя не может быть пустым. Введите имя:"
    if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', value):
        return False, "⚠️ Имя может содержать только буквы, пробелы и дефисы. Попробуйте снова:"
    return True, ""


async def validate_last_name(value: str) -> Tuple[bool, str]:
    """
    Проверяет корректность введённой фамилии.

    Фамилия не должна быть пустой и должна содержать только буквы (русские/латиница),
    пробелы и дефисы.

    Args:
        value (str): введённая пользователем фамилия.

    Returns:
        Tuple[bool, str]: (True, "") если валидация пройдена,
                           (False, сообщение_об_ошибке) в противном случае.
    """
    if not value:
        return False, "❌ Фамилия не может быть пустой. Введите фамилию:"
    if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', value):
        return False, "⚠️ Фамилия может содержать только буквы, пробелы и дефисы. Попробуйте снова:"
    return True, ""


async def validate_birth_date(value: str) -> Tuple[bool, str]:
    """
    Проверяет корректность введённой даты рождения.

    Требования:
        - формат ДД.ММ.ГГГГ
        - дата должна существовать (не 31.02 и т.п.)
        - дата не может быть в будущем
        - возраст от 18 до 100 лет

    Args:
        value (str): строка с датой в формате ДД.ММ.ГГГГ.

    Returns:
        Tuple[bool, str]: (True, "") если валидация пройдена,
                           (False, сообщение_об_ошибке) в противном случае.
    """
    if not re.fullmatch(r'^\d{2}\.\d{2}\.\d{4}$', value):
        return False, "❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:"
    try:
        birth = datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return False, "⚠️ Некорректная дата. Проверьте число, месяц и год:"
    today = date.today()
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    if birth > today:
        return False, "⚠️ Дата рождения не может быть в будущем."
    if age < 18:
        return False, "⛔ К сожалению, программа лояльности доступна только для гостей старше 18 лет."
    if age > 100:
        return False, "⛔ Пожалуйста, введите корректную дату рождения."
    return True, ""


async def validate_email(value: str) -> Tuple[bool, str]:
    """
    Проверяет корректность введённого email-адреса.

    Выполняется простая проверка на наличие символа '@' и точки после него.

    Args:
        value (str): введённый пользователем email.

    Returns:
        Tuple[bool, str]: (True, "") если валидация пройдена,
                           (False, сообщение_об_ошибке) в противном случае.
    """
    if not value:
        return False, "❌ Email не может быть пустым. Введите email:"
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', value):
        return False, "⚠️ Неверный формат email. Попробуйте снова:"
    return True, ""


async def clean_name(value: str) -> str:
    """
    Удаляет лишние пробелы в имени/фамилии (заменяет множественные пробелы на один,
    убирает пробелы в начале и конце).

    Args:
        value (str): исходная строка.

    Returns:
        str: очищенная строка.
    """
    return re.sub(r'\s+', ' ', value).strip()


async def confirm_text(message: MessageCreated,
                       error_text: str = "✍️ Пожалуйста, отправьте текстовое сообщение.") -> bool:
    """
    Проверяет, содержит ли сообщение текст. Если нет – отправляет пользователю
    сообщение об ошибке и возвращает False.

    Args:
        message (MessageCreated): объект события создания сообщения
        error_text (str): текст ошибки, который будет отправлен пользователю

    Returns:
        bool: True, если сообщение содержит текст, иначе False.
    """
    if not message.body.text:
        await message.answer(text=error_text)
        return False
    return True
