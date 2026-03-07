"""
Обработчики для системы модерации
===================================
Содержит функции для:
- меню модератора
- просмотра списков тикетов с фильтрацией и пагинацией
- просмотра деталей тикета
- ответа на тикет
- закрытия тикета
- уведомления модераторов о новых тикетах

Все хендлеры используют корректные методы maxapi:
- Текст сообщения: event.message.body.text
- Редактирование: event.bot.update_message
- Отправка клавиатур: attachments=[keyboard]
- Работа с FSM: context (MemoryContext) передаётся вторым параметром
- Проверка прав модератора через is_moderator
"""

from loguru import logger

from maxapi import Router
from maxapi.types import MessageCreated, MessageCallback, Command
from maxapi.context import MemoryContext

from app.database import db
from app.services.tickets import ticket_service
from app.keyboards.moderation import ModerationKeyboard
from app.keyboards.user_tickets import UserTicketsKeyboard
from app.states.tickets import TicketStates
from app.utils.ticket_formatter import format_ticket_details

import html

router = Router()

# Константы для фильтрации списка тикетов
FILTER_ALL = 'all'
FILTER_OPEN = 'open'
FILTER_IN_PROGRESS = 'progress'

# Соответствие фильтров статусам тикетов (None означает все статусы)
FILTER_STATUS_MAP = {
    FILTER_ALL: None,
    FILTER_OPEN: ['open'],
    FILTER_IN_PROGRESS: ['in_progress'],
}

# Человекочитаемые названия фильтров для заголовков
FILTER_TITLES = {
    FILTER_ALL: "Все тикеты",
    FILTER_OPEN: "Новые тикеты",
    FILTER_IN_PROGRESS: "Тикеты в работе",
}


async def is_moderator(user_id: int) -> bool:
    """Проверяет, является ли пользователь модератором.

    Args:
        user_id (int): ID пользователя.

    Returns:
        bool: True, если пользователь модератор, иначе False.
    """
    return await db.is_user_moderator(user_id)


# ---------- Меню модератора ----------
@router.message_created(Command('mod'))
async def mod_command(event: MessageCreated) -> None:
    """Обработчик команды /mod для открытия меню модератора.

    Если пользователь не модератор, выводит сообщение об ошибке.
    Отображает статистику тикетов и главное меню модератора.
    """
    if not await is_moderator(event.from_user.user_id):
        await event.message.answer(text="❌ У вас нет прав модератора")
        return

    bot = event.bot
    open_count, in_progress_count, avg_response_time = await ticket_service.get_tickets_stats()
    stats_text = (
        f"👨‍💼 *Модератор*\n\n"
        f"📬 Новые тикеты: {open_count}\n"
        f"🔄 В работе: {in_progress_count}\n"
    )
    if avg_response_time is not None:
        stats_text += f"⏱ Среднее время ответа: {avg_response_time} мин\n"
    else:
        stats_text += "⏱ Среднее время ответа: -\n"

    await bot.send_message(
        chat_id=event.chat.id,
        text=stats_text,
        attachments=[ModerationKeyboard.main_menu()]
    )


@router.message_created(Command('Модератор'))
async def moderator_menu(event: MessageCreated) -> None:
    """Обработчик нажатия на кнопку «Модератор» в главном меню (если она есть).

    Аналогичен команде /mod.
    """
    if not await is_moderator(event.from_user.user_id):
        await event.message.answer(text="❌ У вас нет прав модератора")
        return

    bot = event.bot
    open_count, in_progress_count, avg_response_time = await ticket_service.get_tickets_stats()
    stats_text = (
        f"👨‍💼 *Модератор*\n\n"
        f"📬 Новые тикеты: {open_count}\n"
        f"🔄 В работе: {in_progress_count}\n"
    )
    if avg_response_time is not None:
        stats_text += f"⏱ Среднее время ответа: {avg_response_time} мин\n"
    else:
        stats_text += "⏱ Среднее время ответа: -\n"

    await bot.send_message(
        chat_id=event.chat.id,
        text=stats_text,
        attachments=[ModerationKeyboard.main_menu()]
    )


@router.message_callback(Command('mod_main'))
async def mod_main_callback(event: MessageCallback) -> None:
    """Главное меню модератора, вызываемое по callback (например, после возврата из списка).

    Отображает статистику и меню.
    """
    if not await is_moderator(event.user.user_id):
        await event.answer("❌ У вас нет прав модератора")
        return

    bot = event.bot
    open_count, in_progress_count, avg_response_time = await ticket_service.get_tickets_stats()
    stats_text = (
        f"👨‍💼 *Модератор*\n\n"
        f"📬 Новые тикеты: {open_count}\n"
        f"🔄 В работе: {in_progress_count}\n"
    )
    if avg_response_time is not None:
        stats_text += f"⏱ Среднее время ответа: {avg_response_time} мин\n"
    else:
        stats_text += "⏱ Среднее время ответа: -\n"

    await bot.edit_message(
        message_id=event.message.body.mid,
        text=stats_text,
        attachments=[ModerationKeyboard.main_menu()]
    )
    await event.answer("")


# ---------- Список тикетов ----------
@router.message_callback(Command('mod_tickets'))
async def mod_tickets_list(event: MessageCallback) -> None:
    """Обработчик кнопки «Все тикеты» – показывает первую страницу списка.

    Без фильтрации, только пагинация.
    """
    if not await is_moderator(event.user.user_id):
        await event.answer("❌ У вас нет прав модератора")
        return

    bot = event.bot
    tickets, total_count = await ticket_service.get_tickets_page(page=1, per_page=10)
    total_pages = (total_count + 10 - 1) // 10

    if not tickets:
        text = "📭 Нет тикетов"
        await bot.edit_message(
            message_id=event.message.body.mid,
            text=text,
            attachments=[ModerationKeyboard.main_menu()]
        )
        await event.answer("")
        return

    text = f"📋 Все тикеты (страница 1/{total_pages}):"
    await bot.edit_message(
        message_id=event.message.body.mid,
        text=text,
        attachments=[ModerationKeyboard.tickets_list(tickets, current_page=1, total_pages=total_pages)]
    )
    await event.answer("")


@router.message_callback(Command('mod_tickets_all'))
@router.message_callback(Command('mod_tickets_open'))
@router.message_callback(Command('mod_tickets_progress'))
async def mod_tickets_filtered(event: MessageCallback, context: MemoryContext) -> None:
    """Обработчик для отображения списка тикетов с фильтром.

    Фильтр извлекается из имени команды (all/open/progress).
    Сохраняет текущий фильтр в контексте для последующего возврата из деталей тикета.

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку
        context (MemoryContext): контекст FSM для сохранения данных
    """
    if not await is_moderator(event.user.user_id):
        await event.answer("❌ У вас нет прав модератора")
        return

    bot = event.bot
    # Извлекаем фильтр из payload (например, "mod_tickets_all" -> "all")
    filter_key = event.callback.payload.split('_')[-1]
    if filter_key not in FILTER_STATUS_MAP:
        await event.answer("❌ Неизвестный фильтр")
        return

    # Сохраняем текущий фильтр в контексте (для возврата из деталей тикета)
    await context.update_data(current_ticket_filter=filter_key)

    statuses = FILTER_STATUS_MAP[filter_key]
    tickets, total_count = await ticket_service.get_tickets_page(
        page=1,
        per_page=10,
        statuses=statuses
    )
    total_pages = (total_count + 10 - 1) // 10

    if not tickets:
        text = f"📭 {FILTER_TITLES[filter_key]} отсутствуют."
        await bot.edit_message(
            message_id=event.message.body.mid,
            text=text,
            attachments=[ModerationKeyboard.back_to_main()]
        )
        await event.answer("")
        return

    text = f"📋 {FILTER_TITLES[filter_key]} (страница 1/{total_pages}):"
    await bot.edit_message(
        message_id=event.message.body.mid,
        text=text,
        attachments=[ModerationKeyboard.tickets_list(
            tickets,
            current_page=1,
            total_pages=total_pages,
            filter_key=filter_key
        )]
    )
    await event.answer("")


@router.message_callback(Command('mod_tickets_page_all'))
@router.message_callback(Command('mod_tickets_page_open'))
@router.message_callback(Command('mod_tickets_page_progress'))
async def mod_tickets_page_filtered(event: MessageCallback, context: MemoryContext) -> None:
    """Обработчик переключения страниц списка тикетов с фильтром.

    Ожидает callback_data вида "mod_tickets_page_<filter>_<page>".
    Сохраняет текущий фильтр в контексте.

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку.
        context (MemoryContext): контекст FSM для сохранения данных.
    """
    if not await is_moderator(event.user.user_id):
        await event.answer("❌ У вас нет прав модератора")
        return

    bot = event.bot
    parts = event.callback.payload.split('_')
    if len(parts) != 5:
        await event.answer("❌ Неверный формат данных")
        return

    filter_key = parts[3]
    try:
        page = int(parts[4])
    except ValueError:
        await event.answer("❌ Ошибка в номере страницы")
        return

    if filter_key not in FILTER_STATUS_MAP:
        await event.answer("❌ Неизвестный фильтр")
        return

    await context.update_data(current_ticket_filter=filter_key)

    statuses = FILTER_STATUS_MAP[filter_key]
    tickets, total_count = await ticket_service.get_tickets_page(
        page=page,
        per_page=10,
        statuses=statuses
    )
    total_pages = (total_count + 10 - 1) // 10

    if not tickets:
        text = f"📭 {FILTER_TITLES[filter_key]} отсутствуют на странице {page}."
        await bot.edit_message(
            message_id=event.message.body.mid,
            text=text,
            attachments=[ModerationKeyboard.back_to_main()]
        )
        await event.answer("")
        return

    text = f"📋 {FILTER_TITLES[filter_key]} (страница {page}/{total_pages}):"
    await bot.edit_message(
        message_id=event.message.body.mid,
        text=text,
        attachments=[ModerationKeyboard.tickets_list(
            tickets,
            current_page=page,
            total_pages=total_pages,
            filter_key=filter_key
        )]
    )
    await event.answer("")


# ---------- Детали тикета ----------
@router.message_callback(Command('mod_ticket_'))
async def mod_ticket_details(event: MessageCallback, context: MemoryContext) -> None:
    """Показывает детальную информацию по тикету.

    Извлекает ID тикета из payload (ожидается mod_ticket_<id>).
    Получает сохранённый фильтр из контекста для кнопки «Назад».

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку.
        context (MemoryContext): контекст FSM для получения данных.
    """
    if not await is_moderator(event.user.user_id):
        await event.answer("❌ У вас нет прав модератора")
        return

    bot = event.bot
    ticket_id_str = event.callback.payload.replace('mod_ticket_', '')
    try:
        ticket_id = int(ticket_id_str)
    except ValueError:
        await event.answer("❌ Неверный формат")
        return

    context_data = await context.get_data()
    back_filter = context_data.get('current_ticket_filter', FILTER_ALL)

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await event.answer("❌ Тикет не найден")
        return

    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    await bot.edit_message(
        message_id=event.message.body.mid,
        text=ticket_text,
        attachments=[ModerationKeyboard.ticket_details(ticket_id, ticket.status, back_filter)]
    )
    await event.answer("")


# ---------- Ответ на тикет ----------
@router.message_callback(Command('mod_reply_'))
async def mod_reply_to_ticket(event: MessageCallback, context: MemoryContext) -> None:
    """Начало ответа на тикет – устанавливает состояние ожидания ответа.

    Ожидает callback_data вида "mod_reply_<id>".
    Сохраняет ID тикета в контексте и переводит состояние.

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку.
        context (MemoryContext): контекст FSM для сохранения данных и состояния.
    """
    if not await is_moderator(event.user.user_id):
        await event.answer("❌ У вас нет прав модератора")
        return

    bot = event.bot
    ticket_id_str = event.callback.payload.replace('mod_reply_', '')
    try:
        ticket_id = int(ticket_id_str)
    except ValueError:
        await event.answer("❌ Неверный формат")
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await event.answer("❌ Тикет не найден")
        return

    await context.update_data(reply_ticket_id=ticket_id)
    await context.set_state(TicketStates.waiting_for_moderator_reply)

    text = (
        f"📝 *Ответ на тикет #{ticket_id}*\n\n"
        f"Введите ваш ответ пользователю:\n"
        f"(Поддерживается HTML форматирование)"
    )
    await bot.edit_message(
        message_id=event.message.body.mid,
        text=text,
        attachments=[ModerationKeyboard.reply_to_ticket(ticket_id)]
    )
    await event.answer("")


@router.message_created(TicketStates.waiting_for_moderator_reply)
async def mod_send_reply(event: MessageCreated, context: MemoryContext) -> None:
    """Обрабатывает ввод ответа модератора.

    Сохраняет сообщение в историю тикета, уведомляет пользователя,
    обновляет статус тикета и отображает обновлённую карточку.

    Args:
        event (MessageCreated): событие создания сообщения.
        context (MemoryContext): контекст FSM для получения данных и очистки.
    """
    bot = event.bot

    if not event.message.body.text:
        await bot.send_message(
            chat_id=event.chat.id,
            text="✍️ Пожалуйста, отправьте ответ текстовым сообщением."
        )
        return

    if not await is_moderator(event.from_user.user_id):
        await context.clear()
        await bot.send_message(chat_id=event.chat.id, text="❌ У вас нет прав модератора")
        return

    context_data = await context.get_data()
    ticket_id = context_data.get('reply_ticket_id')
    if not ticket_id:
        await context.clear()
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await bot.send_message(chat_id=event.chat.id, text="❌ Тикет не найден")
        await context.clear()
        return

    # Сохраняем ответ в историю
    await ticket_service.add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="moderator",
        sender_id=event.from_user.user_id,
        message=event.message.body.text
    )

    # Обновляем статус, если тикет был открыт
    await ticket_service.update_ticket_status(ticket_id, "in_progress")

    # Уведомляем пользователя
    try:
        await bot.send_message(
            chat_id=ticket.user_id,
            text=(
                f"📬 <b>Ответ на ваш вопрос</b> (тикет #{ticket_id})\n\n"
                f"📝 <b>Ответ от модератора:</b>\n"
                f"{html.escape(event.message.body.text)}"
            ),
            attachments=[UserTicketsKeyboard.notification_keyboard(ticket_id, ticket.status)]
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа пользователю: {e}")

    # Отображаем обновлённый тикет модератору
    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    await bot.send_message(
        chat_id=event.chat.id,
        text=ticket_text,
        attachments=[ModerationKeyboard.ticket_details(ticket_id, ticket.status)]
    )

    await context.clear()


# ---------- Закрытие тикета ----------
@router.message_callback(Command('mod_close_'))
async def mod_close_ticket(event: MessageCallback) -> None:
    """Закрывает тикет (устанавливает статус 'closed').

    Ожидает callback_data вида "mod_close_<id>".
    После закрытия показывает обновлённую карточку тикета.
    """
    if not await is_moderator(event.user.user_id):
        await event.answer("❌ У вас нет прав модератора")
        return

    bot = event.bot
    ticket_id_str = event.callback.payload.replace('mod_close_', '')
    try:
        ticket_id = int(ticket_id_str)
    except ValueError:
        await event.answer("❌ Неверный формат")
        return

    success = await ticket_service.close_ticket(ticket_id)
    if not success:
        await event.answer("❌ Тикет не найден")
        return

    await event.answer("✅ Тикет закрыт")

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        text = "❌ Ошибка при загрузке тикета"
        await bot.edit_message(
            message_id=event.message.body.mid,
            text=text
        )
        return

    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    await bot.edit_message(
        message_id=event.message.body.mid,
        text=ticket_text,
        attachments=[ModerationKeyboard.ticket_details(ticket_id, ticket.status)]
    )
