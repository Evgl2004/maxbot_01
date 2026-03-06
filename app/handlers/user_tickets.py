"""
Обработчики для пользовательского раздела "Мои обращения"
"""

from loguru import logger

from maxbot.router import Router
from maxbot.types import Message, Callback

from app.database import db
from app.database.models import Ticket
from app.services.tickets import ticket_service
from app.keyboards.user_tickets import UserTicketsKeyboard
from app.utils.ticket_formatter import format_ticket_details
from app.states.tickets import UserTicketStates
from app.utils.validation import confirm_text

import html

router = Router()


@router.callback(F.payload == "my_tickets")
async def user_tickets_list(callback: Callback):
    """
    Показывает первую страницу списка тикетов текущего пользователя.
    """
    if callback.payload != "my_tickets":
        return

    bot = callback.dispatcher.bot
    user_id = callback.user.id

    tickets, total_count = await ticket_service.get_tickets_page(
        page=1,
        per_page=5,
        user_id=user_id
    )
    total_pages = (total_count + 5 - 1) // 5

    if not tickets:
        text = (
            "📭 У вас пока нет обращений.\n\n"
            "Чтобы создать обращение, нажмите «❓ Мне только спросить» в меню отдела заботы."
        )
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            reply_markup=UserTicketsKeyboard.back_to_support()
        )
        await bot.answer_callback(callback.callback_id, "")
        return

    text = f"📋 Ваши обращения (страница 1/{total_pages}):"
    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=UserTicketsKeyboard.tickets_list(tickets, current_page=1, total_pages=total_pages)
    )
    await bot.answer_callback(callback.callback_id, "")


@router.callback(F.payload.startswith("user_tickets_page_"))
async def user_tickets_page(callback: Callback):
    """
    Обработчик переключения страниц списка тикетов пользователя.
    """
    if not callback.payload.startswith("user_tickets_page_"):
        return

    bot = callback.dispatcher.bot
    try:
        page = int(callback.payload.split("_")[-1])
    except ValueError:
        await bot.answer_callback(callback.callback_id, "❌ Ошибка")
        return

    user_id = callback.user.id
    tickets, total_count = await ticket_service.get_tickets_page(
        page=page,
        per_page=5,
        user_id=user_id
    )
    total_pages = (total_count + 5 - 1) // 5

    if not tickets:
        text = "📭 На этой странице нет обращений."
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            reply_markup=UserTicketsKeyboard.back_to_support()
        )
        await bot.answer_callback(callback.callback_id, "")
        return

    text = f"📋 Ваши обращения (страница {page}/{total_pages}):"
    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=UserTicketsKeyboard.tickets_list(tickets, current_page=page, total_pages=total_pages)
    )
    await bot.answer_callback(callback.callback_id, "")


@router.callback(F.payload.startswith("user_ticket_"))
async def user_ticket_details(callback: Callback):
    """Показывает детали тикета для пользователя"""
    if not callback.payload.startswith("user_ticket_"):
        return

    bot = callback.dispatcher.bot
    try:
        ticket_id = int(callback.payload.split("_")[-1])
    except ValueError:
        await bot.answer_callback(callback.callback_id, "❌ Неверный формат")
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != callback.user.id:
        await bot.answer_callback(callback.callback_id, "❌ Тикет не найден или доступ запрещён")
        return

    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    await bot.update_message(
        message_id=callback.message.id,
        text=ticket_text,
        reply_markup=UserTicketsKeyboard.ticket_details(ticket_id, ticket.status),
        format="html"
    )
    await bot.answer_callback(callback.callback_id, "")


@router.callback(F.payload.startswith("user_reply_"))
async def user_reply_to_ticket(callback: Callback):
    """Начало ответа на тикет пользователем"""
    if not callback.payload.startswith("user_reply_"):
        return

    bot = callback.dispatcher.bot
    try:
        ticket_id = int(callback.payload.split("_")[-1])
    except ValueError:
        await bot.answer_callback(callback.callback_id, "❌ Ошибка")
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != callback.user.id:
        await bot.answer_callback(callback.callback_id, "❌ Доступ запрещён")
        return

    if ticket.status == 'closed':
        await bot.answer_callback(callback.callback_id, "❌ Тикет закрыт, ответ невозможен")
        return

    await callback.update_data(reply_ticket_id=ticket_id)
    await callback.set_state(UserTicketStates.waiting_for_reply)

    text = (
        f"📝 *Ответ на тикет #{ticket_id}*\n\n"
        f"Введите ваш ответ:"
    )
    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=UserTicketsKeyboard.cancel_reply(ticket_id),
        format="markdown"
    )
    await bot.answer_callback(callback.callback_id, "")


@router.message()
async def user_send_reply(message: Message):
    """
    Обрабатывает ответ пользователя на тикет.
    """
    current_state = await message.get_state()
    if current_state != UserTicketStates.waiting_for_reply.full_name():
        return

    bot = message.dispatcher.bot

    if not message.text:
        await bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, отправьте текстовое сообщение."
        )
        return

    data = await message.get_data()
    ticket_id = data.get("reply_ticket_id")
    if not ticket_id:
        await message.reset_state()
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != message.sender.id:
        await bot.send_message(chat_id=message.chat.id, text="❌ Ошибка доступа")
        await message.reset_state()
        return

    # Сохраняем ответ пользователя в историю
    await ticket_service.add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="user",
        sender_id=message.sender.id,
        message=message.text
    )

    # Если тикет был открыт, переводим его в статус "в работе"
    if ticket.status == 'open':
        await ticket_service.update_ticket_status(ticket_id, 'in_progress')

    # Уведомляем модераторов о новом сообщении
    await notify_moderators_new_message(bot, ticket, message.text)

    # Получаем обновлённую историю переписки
    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    # Отправляем пользователю обновлённую карточку тикета
    await bot.send_message(
        chat_id=message.chat.id,
        text=ticket_text,
        reply_markup=UserTicketsKeyboard.ticket_details(ticket_id, ticket.status),
        format="html"
    )
    await message.reset_state()


async def notify_moderators_new_message(bot, ticket: Ticket, message_text: str):
    """
    Уведомляет всех модераторов о новом сообщении от пользователя в тикете.
    """
    try:
        moderators = await db.get_moderators()
        for moderator in moderators:
            try:
                await bot.send_message(
                    chat_id=moderator.id,
                    text=(
                        f"📬 <b>Новое сообщение от пользователя</b>\n\n"
                        f"🎫 Тикет #{ticket.id}\n"
                        f"👤 Пользователь: {html.escape(ticket.user_username or ticket.user_first_name or str(ticket.user_id))}\n"
                        f"💬 Сообщение: {html.escape(message_text[:100])}{'…' if len(message_text) > 100 else ''}"
                    ),
                    format="html"
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления модератора {moderator.id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при получении списка модераторов: {e}")
