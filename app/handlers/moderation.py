"""
Обработчики для системы модерации
"""

from loguru import logger

from maxbot.router import Router
from maxbot.types import Message, Callback
from maxbot.filters import F

from app.database import db
from app.services.tickets import ticket_service
from app.keyboards.moderation import ModerationKeyboard
from app.keyboards.user_tickets import UserTicketsKeyboard
from app.states.tickets import TicketStates
from app.utils.validation import confirm_text
from app.utils.ticket_formatter import format_ticket_details

import html

router = Router()

# Константы фильтров
FILTER_ALL = 'all'
FILTER_OPEN = 'open'
FILTER_IN_PROGRESS = 'progress'

# Соответствие фильтров статусам
FILTER_STATUS_MAP = {
    FILTER_ALL: None,
    FILTER_OPEN: ['open'],
    FILTER_IN_PROGRESS: ['in_progress'],
}

# Названия для заголовков
FILTER_TITLES = {
    FILTER_ALL: "Все тикеты",
    FILTER_OPEN: "Новые тикеты",
    FILTER_IN_PROGRESS: "Тикеты в работе",
}


async def is_moderator(user_id: int) -> bool:
    """Проверка, является ли пользователь модератором"""
    return await db.is_user_moderator(user_id)


@router.message(F.text == "👨‍💼 Модератор")
async def moderator_menu(message: Message):
    """Меню модератора"""
    if not await is_moderator(message.sender.id):
        await message.dispatcher.bot.send_message(
            chat_id=message.chat.id,
            text="❌ У вас нет прав модератора"
        )
        return

    bot = message.dispatcher.bot
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
        chat_id=message.chat.id,
        text=stats_text,
        reply_markup=ModerationKeyboard.main_menu()
    )


@router.callback()
async def mod_main_callback(callback: Callback):
    """Главное меню модератора (callback)"""
    if not await is_moderator(callback.user.id):
        await callback.dispatcher.bot.answer_callback(
            callback.callback_id,
            "❌ У вас нет прав модератора"
        )
        return

    bot = callback.dispatcher.bot
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

    await bot.update_message(
        message_id=callback.message.id,
        text=stats_text,
        reply_markup=ModerationKeyboard.main_menu(),
        format="markdown"
    )
    await bot.answer_callback(callback.callback_id, "")


@router.callback()
async def mod_tickets_list(callback: Callback):
    """
    Обработчик кнопки «Все тикеты» – показывает первую страницу списка.
    """
    if not await is_moderator(callback.user.id):
        await callback.dispatcher.bot.answer_callback(
            callback.callback_id,
            "❌ У вас нет прав модератора"
        )
        return

    bot = callback.dispatcher.bot
    tickets, total_count = await ticket_service.get_tickets_page(page=1, per_page=10)
    total_pages = (total_count + 10 - 1) // 10

    if not tickets:
        text = "📭 Нет тикетов"
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            reply_markup=ModerationKeyboard.main_menu()
        )
        await bot.answer_callback(callback.callback_id, "")
        return

    text = f"📋 Все тикеты (страница 1/{total_pages}):"
    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=ModerationKeyboard.tickets_list(tickets, current_page=1, total_pages=total_pages)
    )
    await bot.answer_callback(callback.callback_id, "")


@router.callback()
async def mod_tickets_filtered(callback: Callback):
    """
    Обработчик для отображения списка тикетов с фильтром.
    Ожидает callback_data вида mod_tickets_all, mod_tickets_open, mod_tickets_in_progress.
    """
    if not await is_moderator(callback.user.id):
        await callback.dispatcher.bot.answer_callback(
            callback.callback_id,
            "❌ У вас нет прав модератора"
        )
        return

    bot = callback.dispatcher.bot
    filter_key = callback.payload.split("_")[-1]
    if filter_key not in FILTER_STATUS_MAP:
        await bot.answer_callback(callback.callback_id, "❌ Неизвестный фильтр")
        return

    # Сохраняем текущий фильтр в состояние
    await callback.update_data(current_ticket_filter=filter_key)

    statuses = FILTER_STATUS_MAP[filter_key]
    tickets, total_count = await ticket_service.get_tickets_page(
        page=1,
        per_page=10,
        statuses=statuses
    )
    total_pages = (total_count + 10 - 1) // 10

    if not tickets:
        text = f"📭 {FILTER_TITLES[filter_key]} отсутствуют."
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            reply_markup=ModerationKeyboard.back_to_main()
        )
        await bot.answer_callback(callback.callback_id, "")
        return

    text = f"📋 {FILTER_TITLES[filter_key]} (страница 1/{total_pages}):"
    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=ModerationKeyboard.tickets_list(
            tickets,
            current_page=1,
            total_pages=total_pages,
            filter_key=filter_key
        )
    )
    await bot.answer_callback(callback.callback_id, "")


@router.callback()
async def mod_tickets_page_filtered(callback: Callback):
    """
    Обработчик переключения страниц списка тикетов с фильтром.
    Ожидает callback_data вида "mod_tickets_page_all_2", "mod_tickets_page_open_1" и т.д.
    """
    if not await is_moderator(callback.user.id):
        await callback.dispatcher.bot.answer_callback(
            callback.callback_id,
            "❌ У вас нет прав модератора"
        )
        return

    bot = callback.dispatcher.bot
    parts = callback.payload.split("_")
    if len(parts) != 5:  # ["mod", "tickets", "page", filter, page_num]
        await bot.answer_callback(callback.callback_id, "❌ Неверный формат данных")
        return

    filter_key = parts[3]
    try:
        page = int(parts[4])
    except ValueError:
        await bot.answer_callback(callback.callback_id, "❌ Ошибка в номере страницы")
        return

    if filter_key not in FILTER_STATUS_MAP:
        await bot.answer_callback(callback.callback_id, "❌ Неизвестный фильтр")
        return

    await callback.update_data(current_ticket_filter=filter_key)

    statuses = FILTER_STATUS_MAP[filter_key]
    tickets, total_count = await ticket_service.get_tickets_page(
        page=page,
        per_page=10,
        statuses=statuses
    )
    total_pages = (total_count + 10 - 1) // 10

    if not tickets:
        text = f"📭 {FILTER_TITLES[filter_key]} отсутствуют на странице {page}."
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            reply_markup=ModerationKeyboard.back_to_main()
        )
        await bot.answer_callback(callback.callback_id, "")
        return

    text = f"📋 {FILTER_TITLES[filter_key]} (страница {page}/{total_pages}):"
    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=ModerationKeyboard.tickets_list(
            tickets,
            current_page=page,
            total_pages=total_pages,
            filter_key=filter_key
        )
    )
    await bot.answer_callback(callback.callback_id, "")


@router.callback()
async def mod_ticket_details(callback: Callback):
    """
    Показывает детальную информацию по тикету, включая всю историю переписки.
    """
    if not await is_moderator(callback.user.id):
        await callback.dispatcher.bot.answer_callback(
            callback.callback_id,
            "❌ У вас нет прав модератора"
        )
        return

    bot = callback.dispatcher.bot
    try:
        ticket_id = int(callback.payload.split("_")[-1])
    except ValueError:
        await bot.answer_callback(callback.callback_id, "❌ Неверный формат данных")
        return

    data = await callback.get_data()
    back_filter = data.get("current_ticket_filter", FILTER_ALL)

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await bot.answer_callback(callback.callback_id, "❌ Тикет не найден")
        return

    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    await bot.update_message(
        message_id=callback.message.id,
        text=ticket_text,
        reply_markup=ModerationKeyboard.ticket_details(ticket_id, ticket.status, back_filter),
        format="html"
    )
    await bot.answer_callback(callback.callback_id, "")


@router.callback()
async def mod_reply_to_ticket(callback: Callback):
    """Ответ на тикет"""
    if not await is_moderator(callback.user.id):
        await callback.dispatcher.bot.answer_callback(
            callback.callback_id,
            "❌ У вас нет прав модератора"
        )
        return

    bot = callback.dispatcher.bot
    ticket_id = int(callback.payload.split("_")[-1])
    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await bot.answer_callback(callback.callback_id, "❌ Тикет не найден")
        return

    await callback.update_data(reply_ticket_id=ticket_id)
    await callback.set_state(TicketStates.waiting_for_moderator_reply)

    text = (
        f"📝 *Ответ на тикет #{ticket_id}*\n\n"
        f"Введите ваш ответ пользователю:\n"
        f"(Поддерживается HTML форматирование)"
    )
    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=ModerationKeyboard.reply_to_ticket(ticket_id),
        format="markdown"
    )
    await bot.answer_callback(callback.callback_id, "")


@router.message()
async def mod_send_reply(message: Message):
    # Проверяем состояние
    current_state = await message.get_state()
    if current_state != TicketStates.waiting_for_moderator_reply.full_name():
        return

    bot = message.dispatcher.bot

    if not message.text:
        await bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, отправьте ответ текстовым сообщением."
        )
        return

    if not await is_moderator(message.sender.id):
        await message.reset_state()
        await bot.send_message(chat_id=message.chat.id, text="❌ У вас нет прав модератора")
        return

    data = await message.get_data()
    ticket_id = data.get("reply_ticket_id")
    if not ticket_id:
        await message.reset_state()
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await bot.send_message(chat_id=message.chat.id, text="❌ Тикет не найден")
        await message.reset_state()
        return

    await ticket_service.add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="moderator",
        sender_id=message.sender.id,
        message=message.text
    )

    await ticket_service.update_ticket_status(ticket_id, "in_progress")

    try:
        await bot.send_message(
            chat_id=ticket.user_id,
            text=(
                f"📬 <b>Ответ на ваш вопрос</b> (тикет #{ticket_id})\n\n"
                f"📝 <b>Ответ от модератора:</b>\n"
                f"{html.escape(message.text)}"
            ),
            reply_markup=UserTicketsKeyboard.notification_keyboard(ticket_id, ticket.status),
            format="html"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа пользователю: {e}")

    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    await bot.send_message(
        chat_id=message.chat.id,
        text=ticket_text,
        reply_markup=ModerationKeyboard.ticket_details(ticket_id, ticket.status),
        format="html"
    )

    await message.reset_state()


@router.message(F.text == "/mod")
async def mod_command(message: Message):
    """Команда для открытия меню модератора"""
    if not await is_moderator(message.sender.id):
        await message.dispatcher.bot.send_message(
            chat_id=message.chat.id,
            text="❌ У вас нет прав модератора"
        )
        return

    bot = message.dispatcher.bot
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
        chat_id=message.chat.id,
        text=stats_text,
        reply_markup=ModerationKeyboard.main_menu(),
        format="markdown"
    )


@router.callback()
async def mod_close_ticket(callback: Callback):
    """Закрыть тикет (установить статус closed и время закрытия)"""
    if not await is_moderator(callback.user.id):
        await callback.dispatcher.bot.answer_callback(
            callback.callback_id,
            "❌ У вас нет прав модератора"
        )
        return

    bot = callback.dispatcher.bot
    ticket_id = int(callback.payload.split("_")[-1])

    success = await ticket_service.close_ticket(ticket_id)
    if not success:
        await bot.answer_callback(callback.callback_id, "❌ Тикет не найден")
        return

    await bot.answer_callback(callback.callback_id, "✅ Тикет закрыт")

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        text = "❌ Ошибка при загрузке тикета"
        await bot.update_message(
            message_id=callback.message.id,
            text=text
        )
        return

    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    await bot.update_message(
        message_id=callback.message.id,
        text=ticket_text,
        reply_markup=ModerationKeyboard.ticket_details(ticket_id, ticket.status),
        format="html"
    )
