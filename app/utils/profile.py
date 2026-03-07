"""Общие функции для работы с профилем пользователя."""

from typing import Union

from maxapi.types import MessageCreated, MessageCallback
from maxapi.context import MemoryContext

from app.database import db
from app.keyboards.registration import get_review_keyboard


async def show_profile_review(
    event: Union[MessageCreated, MessageCallback],
    context: MemoryContext,
    target_state=None
) -> None:
    """
    Показывает пользователю его текущие данные в виде анкеты с кнопками «Всё верно» / «Изменить».

    Функция используется в процессах регистрации и обновления legacy-пользователей.
    В зависимости от типа события (сообщение или callback) либо отправляет новое сообщение,
    либо редактирует текущее. После отображения анкеты устанавливает целевое состояние FSM,
    если оно передано.

    Args:
        event (Union[MessageCreated, MessageCallback]): объект события, инициировавшего показ анкеты
        context (MemoryContext): контекст FSM для последующей установки состояния
        target_state: целевое состояние, в которое нужно перевести пользователя после показа анкеты
                      (обычно Registration.waiting_for_review или LegacyUpgrade.waiting_for_review)

    Returns:
        None
    """
    user_id = event.from_user.user_id if isinstance(event, MessageCreated) else event.user.user_id
    bot = event.bot

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

    if isinstance(event, MessageCreated):
        await bot.send_message(
            chat_id=event.chat.id,
            text=text,
            attachments=[get_review_keyboard()]
        )
    else:
        await bot.edit_message(
            message_id=event.message.id,
            text=text,
            attachments=[get_review_keyboard()]
        )
        await bot.answer_callback(event.callback_id, "")

    if target_state:
        await context.set_state(target_state)
