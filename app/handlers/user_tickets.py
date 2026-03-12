"""
Обработчики для пользовательского раздела «Мои обращения»
=============================================================
Содержит функции для:
- просмотра списка тикетов текущего пользователя (с пагинацией)
- просмотра деталей тикета
- ответа на тикет пользователем
- обработки текста ответа
- уведомления модераторов о новом сообщении.

Все хендлеры используют корректные методы maxapi:
- Текст сообщения: event.message.body.text
- Редактирование: event.bot.edit_message с обязательным message_id
- Отправка клавиатур: attachments=[keyboard]
- Работа с FSM: context (MemoryContext) передаётся вторым параметром
- Ответ на callback: await event.answer("")
- Отправка простых сообщений: bot.send_message
"""

from loguru import logger

from maxapi import Router
from maxapi.types import MessageCreated, MessageCallback
from maxapi.context import MemoryContext
from maxapi.enums.parse_mode import ParseMode
from maxapi import F

from app.database import db
from app.database.models import Ticket
from app.services.tickets import ticket_service
from app.keyboards.user_tickets import UserTicketsKeyboard
from app.utils.ticket_formatter import format_ticket_details
from app.states.tickets import UserTicketStates

import html

router = Router()


# ---------- Список обращений (первая страница) ----------
@router.message_callback(F.callback.payload == 'my_tickets')
async def user_tickets_list(event: MessageCallback) -> None:
    """
    Показывает первую страницу списка тикетов текущего пользователя.

    Запрашивает из сервиса первую страницу тикетов (по 5 на странице),
    формирует клавиатуру со списком и кнопками пагинации.
    Если тикетов нет, выводит информационное сообщение.

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку.
    """

    logger.info(f"user_tickets_list: вызван для user {event.from_user.user_id}")

    bot = event.bot
    user_id = event.from_user.user_id

    # Получаем первую страницу тикетов пользователя (по 5 на странице)
    tickets, total_count = await ticket_service.get_tickets_page(
        page=1,
        per_page=5,
        user_id=user_id
    )
    logger.info(f"user_tickets_list: получено {len(tickets)} тикетов на странице, всего {total_count}")
    total_pages = (total_count + 5 - 1) // 5

    if not tickets:
        text = (
            "📭 У вас пока нет обращений.\n\n"
            "Чтобы создать обращение, нажмите «❓ Мне только спросить» в меню отдела заботы."
        )
        await bot.edit_message(
            message_id=event.message.body.mid,
            text=text,
            attachments=[UserTicketsKeyboard.back_to_support()]
        )
        await event.answer("")
        return

    text = f"📋 Ваши обращения (страница 1/{total_pages}):"
    logger.info(f"user_tickets_list: передаём в клавиатуру {len(tickets)} тикетов")

    # Сначала отвечаем на callback
    await event.answer("")

    # Удаляем старое сообщение
    await bot.delete_message(event.message.body.mid)

    # Отправляем новое сообщение с клавиатурой
    await bot.send_message(
        chat_id=event.message.recipient.chat_id,
        text=text,
        attachments=[UserTicketsKeyboard.tickets_list(tickets, current_page=1, total_pages=total_pages)]
    )


# ---------- Переключение страниц ----------
@router.message_callback(F.callback.payload.startswith('user_tickets_page_'))
async def user_tickets_page(event: MessageCallback) -> None:
    """
    Обработчик переключения страниц списка тикетов пользователя.

    Ожидает callback_data вида "user_tickets_page_2", где число — номер страницы.
    Извлекает номер, запрашивает соответствующую страницу и обновляет сообщение.

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку.
    """
    bot = event.bot
    # Извлекаем номер страницы из payload
    page_str = event.callback.payload.replace('user_tickets_page_', '')
    try:
        page = int(page_str)
    except ValueError:
        await event.answer("❌ Ошибка")
        return

    user_id = event.from_user.user_id
    tickets, total_count = await ticket_service.get_tickets_page(
        page=page,
        per_page=5,
        user_id=user_id
    )
    total_pages = (total_count + 5 - 1) // 5

    if not tickets:
        text = "📭 На этой странице нет обращений."
        await bot.edit_message(
            message_id=event.message.body.mid,
            text=text,
            attachments=[UserTicketsKeyboard.back_to_support()]
        )
        await event.answer("")
        return

    text = f"📋 Ваши обращения (страница {page}/{total_pages}):"
    await bot.edit_message(
        message_id=event.message.body.mid,
        text=text,
        attachments=[UserTicketsKeyboard.tickets_list(tickets, current_page=page, total_pages=total_pages)]
    )
    await event.answer("")


# ---------- Детали тикета ----------
@router.message_callback(F.callback.payload.startswith('user_ticket_'))
async def user_ticket_details(event: MessageCallback) -> None:
    """
    Показывает детали тикета для пользователя.

    Ожидает callback_data вида "user_ticket_123". Извлекает ID тикета,
    проверяет принадлежность текущему пользователю, получает историю переписки
    и отображает отформатированную карточку тикета.

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку.
    """
    bot = event.bot
    ticket_id_str = event.callback.payload.replace('user_ticket_', '')
    try:
        ticket_id = int(ticket_id_str)
    except ValueError:
        await event.answer("❌ Неверный формат")
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != event.from_user.user_id:
        await event.answer("❌ Тикет не найден или доступ запрещён")
        return

    logger.info(f"user_ticket_details: статус тикета из БД: {ticket.status}")

    messages = await ticket_service.get_ticket_messages(ticket_id)

    logger.info(f"user_ticket_details: получено {len(messages)} сообщений, "
                f"тип первого: {type(messages[0]).__name__ if messages else 'None'}")

    ticket_text = format_ticket_details(ticket, messages)

    # Сначала отвечаем на callback
    await event.answer("")

    # Удаляем старое сообщение
    await bot.delete_message(event.message.body.mid)

    # Отправляем новое сообщение с клавиатурой
    await bot.send_message(
        chat_id=event.message.recipient.chat_id,
        text=ticket_text,
        attachments=[UserTicketsKeyboard.ticket_details(ticket_id, ticket.status)],
        parse_mode=ParseMode.HTML
    )
    logger.info("user_ticket_details: сообщение отправлено")


# ---------- Начало ответа на тикет ----------
@router.message_callback(F.callback.payload.startswith('user_reply_'))
async def user_reply_to_ticket(event: MessageCallback, context: MemoryContext) -> None:
    """
    Начало ответа на тикет – устанавливает состояние ожидания ответа.

    Ожидает callback_data вида "user_reply_123". Проверяет, что тикет не закрыт,
    сохраняет его ID в контексте и переводит состояние в waiting_for_reply.

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку.
        context (MemoryContext): контекст FSM для сохранения данных и состояния.
    """
    bot = event.bot
    ticket_id_str = event.callback.payload.replace('user_reply_', '')
    try:
        ticket_id = int(ticket_id_str)
    except ValueError:
        await event.answer("❌ Ошибка")
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != event.from_user.user_id:
        await event.answer("❌ Доступ запрещён")
        return

    if ticket.status == 'closed':
        await event.answer("❌ Тикет закрыт, ответ невозможен")
        return

    await context.update_data(reply_ticket_id=ticket_id)
    await context.set_state(UserTicketStates.waiting_for_reply)

    text = (
        f"📝 *Ответ на тикет #{ticket_id}*\n\n"
        f"Введите ваш ответ:"
    )

    # Сначала отвечаем на callback, чтобы убрать состояние загрузки
    await event.answer("")

    # Удаляем старое сообщение с деталями тикета и его клавиатурой
    await bot.delete_message(event.message.body.mid)

    await bot.send_message(
        chat_id=event.message.recipient.chat_id,
        text=text,
        attachments=[UserTicketsKeyboard.cancel_reply(ticket_id)],
        parse_mode=ParseMode.MARKDOWN
    )

    await context.update_data(reply_prompt_message_id=event.message.body.mid)


@router.message_callback(F.callback.payload.startswith('user_cancel_reply_'))
async def user_cancel_reply(event: MessageCallback, context: MemoryContext) -> None:
    """
    Отмена ответа на тикет пользователем: очищает состояние и показывает детали тикета.
    """
    bot = event.bot
    ticket_id_str = event.callback.payload.replace('user_cancel_reply_', '')
    try:
        ticket_id = int(ticket_id_str)
    except ValueError:
        await event.answer("❌ Ошибка")
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != event.from_user.user_id:
        await event.answer("❌ Доступ запрещён")
        return

    # Очищаем контекст
    await context.clear()

    # Показываем детали тикета
    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    await bot.edit_message(
        message_id=event.message.body.mid,
        text=ticket_text,
        attachments=[UserTicketsKeyboard.ticket_details(ticket_id, ticket.status)],
        parse_mode=ParseMode.HTML
    )
    await event.answer("")


# ---------- Обработка ввода ответа пользователя ----------
@router.message_created(UserTicketStates.waiting_for_reply)
async def user_send_reply(event: MessageCreated, context: MemoryContext) -> None:
    """
    Обрабатывает ответ пользователя на тикет.

    Сохраняет сообщение в историю тикета, уведомляет модераторов,
    обновляет статус тикета и показывает пользователю обновлённую карточку.

    Args:
        event (MessageCreated): событие создания сообщения
        context (MemoryContext): контекст FSM для получения данных и очистки
    """
    bot = event.bot

    if not event.message.body.text:
        await bot.send_message(
            chat_id=event.chat.chat_id,
            text="✍️ Пожалуйста, отправьте текстовое сообщение."
        )
        return

    context_data = await context.get_data()
    ticket_id = context_data.get('reply_ticket_id')
    if not ticket_id:
        await context.clear()
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != event.from_user.user_id:
        await bot.send_message(chat_id=event.chat.chat_id, text="❌ Ошибка доступа")
        await context.clear()
        return

    # Сохраняем ответ пользователя в историю
    await ticket_service.add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="user",
        sender_id=event.from_user.user_id,
        message=event.message.body.text
    )

    # Удаляем предыдущее сообщение с кнопкой "Отмена"
    context_data = await context.get_data()
    prompt_msg_id = context_data.get('reply_prompt_message_id')
    if prompt_msg_id:
        try:
            await bot.delete_message(prompt_msg_id)
            logger.info(f"Удалено сообщение с подсказкой ответа {prompt_msg_id}")
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение с подсказкой: {e}")

    # Если тикет был открыт, переводим его в статус "в работе"
    if ticket.status == 'open':
        await ticket_service.update_ticket_status(ticket_id, 'in_progress')

    # Уведомляем модераторов о новом сообщении
    await _notify_moderators_new_message(bot, ticket, event.message.body.text)

    # Получаем обновлённую историю и показываем карточку
    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    await bot.send_message(
        chat_id=event.chat.chat_id,
        text=ticket_text,
        attachments=[UserTicketsKeyboard.ticket_details(ticket_id, ticket.status)],
        parse_mode=ParseMode.HTML
    )
    await context.clear()


# ---------- Вспомогательная функция для уведомления модераторов ----------
async def _notify_moderators_new_message(bot, ticket: Ticket, message_text: str) -> None:
    """
    Уведомляет всех модераторов о новом сообщении от пользователя в тикете.

    Args:
        bot: экземпляр бота для отправки сообщений
        ticket (Ticket): объект тикета
        message_text (str): текст нового сообщения
    """
    try:
        moderators = await db.get_moderators()
        user_display = html.escape(ticket.user_username or ticket.user_first_name or str(ticket.user_id))
        for moderator in moderators:
            try:
                await bot.send_message(
                    user_id=moderator.id,
                    text=(
                        f"📬 <b>Новое сообщение от пользователя</b>\n\n"
                        f"🎫 Тикет #{ticket.id}\n"
                        f"👤 Пользователь: {html.escape(user_display)}\n"
                        f"💬 Сообщение: {html.escape(message_text[:100])}{'…' if len(message_text) > 100 else ''}"
                    ),
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления модератора {moderator.id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при получении списка модераторов: {e}")
