"""Общие функции для работы с профилем пользователя"""

from typing import Union

from maxbot.types import Message, Callback

from app.database import db
from app.keyboards.registration import get_review_keyboard


async def show_profile_review(event: Union[Message, Callback], target_state=None):
    """
    Показывает пользователю его текущие данные в виде анкеты с кнопками «Всё верно» / «Изменить».

    Args:
        event (Union[Message, Callback]): Объект события (сообщение или callback)
        target_state: Состояние для установки после показа (опционально)
    """
    user_id = event.sender.id if isinstance(event, Message) else event.user.id
    bot = event.dispatcher.bot

    user = await db.get_user(user_id)
    if not user:
        return

    gender_text = "мужской" if user.gender == "male" else "женский" if user.gender == "female" else "не указан"
    birth_text = user.birth_date.strftime('%d.%m.%Y') if user.birth_date else "не указана"
    text = (
        "📋 *Проверьте введённые данные:*\n\n"
        f"👤 *Имя:* {user.first_name_input or 'не указано'}\n"
        f"👥 *Фамилия:* {user.last_name_input or 'не указано'}\n"
        f"📞 *Телефон:* {user.phone_number or 'не указан'}\n"
        f"⚥ *Пол:* {gender_text}\n"
        f"🎂 *Дата рождения:* {birth_text}\n"
        f"📧 *Email:* {user.email or 'не указан'}\n\n"
        "Всё верно?"
    )

    if isinstance(event, Message):
        await bot.send_message(
            chat_id=event.chat.id,
            text=text,
            reply_markup=get_review_keyboard(),
            format="markdown"
        )
    else:
        await bot.update_message(
            message_id=event.message.id,
            text=text,
            reply_markup=get_review_keyboard(),
            format="markdown"
        )
        await bot.answer_callback(event.callback_id, "")

    # Устанавливаем состояние, если передано
    if target_state:
        await event.set_state(target_state)
