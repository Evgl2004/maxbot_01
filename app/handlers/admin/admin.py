"""
Обработчики меню Администратора
=================================
Содержит функции для:
- команды /admin
- начала создания рассылки
- приёма сообщения для рассылки
- добавления кнопки
- подтверждения рассылки
- запуска рассылки через сервис BroadcastService
"""

import re

from maxapi import Router
from maxapi.types import MessageCreated, MessageCallback, Command
from maxapi.context import MemoryContext

from app.config import settings
from app.database import db
from app.states import AdminStates
from app.keyboards import AdminKeyboards

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return settings.is_admin(user_id)


# ---------- Команда /admin ----------
@router.message_created(Command('admin'))
async def admin_command(event: MessageCreated) -> None:
    """
    Обработчик команды /admin. Показывает статистику и меню администратора.
    """
    if not is_admin(event.sender.user_id):
        await event.message.answer(text="❌ У вас нет прав администратора")
        return

    bot = event.bot
    stats = await db.get_bot_stats()
    if not stats:
        stats = await db.update_bot_stats()

    total_users = await db.get_users_count()
    active_users = await db.get_active_users_count()
    last_restart = stats.last_restart.strftime("%d.%m.%Y %H:%M:%S")

    text = (
        f"🔧 <b>Админская панель</b>\n\n"
        f"📊 <b>Статистика бота:</b>\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"✅ Активных пользователей: <b>{active_users}</b>\n"
        f"🟢 Статус: <b>{stats.status}</b>\n"
        f"🕐 Последний запуск: <b>{last_restart}</b>\n\n"
        f"Выберите действие:"
    )
    await bot.send_message(
        chat_id=event.chat.id,
        text=text,
        attachments=[AdminKeyboards.main_admin_menu()]
    )


# ---------- Начало создания рассылки ----------
@router.message_callback(Command('admin_broadcast'))
async def start_broadcast(event: MessageCallback, context: MemoryContext) -> None:
    """
    Нажатие на кнопку «Рассылка» – переход к вводу сообщения.
    """
    if not is_admin(event.user.user_id):
        await event.answer("❌ Нет прав")
        return

    bot = event.bot
    await context.set_state(AdminStates.broadcast_message)

    await bot.update_message(
        message_id=event.message.id,
        text="📤 <b>Создание рассылки</b>\n\n"
             "Отправьте сообщение любого типа (текст, фото, видео, документ и т.д.), "
             "которое хотите разослать всем пользователям бота.\n\n"
             "Для отмены введите /cancel",
    )
    await event.answer("")


# ---------- Получение сообщения для рассылки ----------
@router.message_created(AdminStates.broadcast_message)
async def receive_broadcast_message(event: MessageCreated, context: MemoryContext) -> None:
    """
    Получение сообщения, которое будет разослано.
    """
    if not is_admin(event.sender.user_id):
        await context.clear()
        return

    bot = event.bot
    # Сохраняем само сообщение в контексте (объект MessageCreated хранить нельзя, лучше сохранить его данные)
    # Вместо сохранения всего сообщения будем использовать прямую передачу в BroadcastService позже.
    # Пока просто запомним, что сообщение получено, и перейдём к выбору кнопки.
    await context.update_data(broadcast_message_received=True)

    users_count = await db.get_active_users_count()
    await bot.send_message(
        chat_id=event.chat.id,
        text=f"✅ <b>Сообщение получено!</b>\n\n"
             f"👥 Количество получателей: <b>{users_count}</b>\n\n"
             f"Хотите добавить кнопку к сообщению?",
        attachments=[AdminKeyboards.broadcast_add_button()]
    )
    # Остаёмся в том же состоянии для выбора (AdminStates.broadcast_message)
    await context.set_state(AdminStates.broadcast_message)


# ---------- Добавление кнопки ----------
@router.message_callback(Command('broadcast_add_button'))
async def add_button_to_broadcast(event: MessageCallback, context: MemoryContext) -> None:
    """
    Пользователь выбрал «Добавить кнопку». Переходим к вводу данных кнопки.
    """
    if not is_admin(event.user.user_id):
        await event.answer("❌ Нет прав")
        return

    bot = event.bot
    await context.set_state(AdminStates.broadcast_button)

    await bot.update_message(
        message_id=event.message.id,
        text="🔗 <b>Добавление кнопки</b>\n\n"
             "Отправьте кнопку в формате:\n"
             "<code>Текст кнопки | https://example.com</code>\n\n"
             "Пример:\n"
             "<code>Наш сайт | https://example.com</code>\n\n"
             "Для отмены введите /cancel",
    )
    await event.answer("")


# ---------- Получение данных кнопки ----------
@router.message_created(AdminStates.broadcast_button)
async def receive_broadcast_button(event: MessageCreated, context: MemoryContext) -> None:
    """
    Обрабатывает ввод кнопки (текст и URL).
    """
    if not is_admin(event.sender.user_id):
        await context.clear()
        return

    bot = event.bot
    if not event.message.body.text:                           # <-- исправлено
        await bot.send_message(
            chat_id=event.chat.id,
            text="✍️ Пожалуйста, отправьте текстовое сообщение."
        )
        return

    button_pattern = r"^(.+?)\s*\|\s*(https?://.+)$"
    match = re.match(button_pattern, event.message.body.text.strip())  # <-- исправлено

    if not match:
        await bot.send_message(
            chat_id=event.chat.id,
            text="❌ <b>Неверный формат кнопки!</b>\n\n"
                 "Используйте формат:\n"
                 "<code>Текст кнопки | https://example.com</code>\n\n"
                 "Попробуйте еще раз или введите /cancel для отмены",
        )
        return

    button_text = match.group(1).strip()
    button_url = match.group(2).strip()

    # Сохраняем кнопку в контексте
    await context.update_data(
        button_text=button_text,
        button_url=button_url
    )

    # Показываем превью кнопки
    preview_keyboard = AdminKeyboards.create_custom_button(button_text, button_url)

    await bot.send_message(
        chat_id=event.chat.id,
        text=f"✅ <b>Кнопка создана!</b>\n\n"
             f"📝 Текст: <b>{button_text}</b>\n"
             f"🔗 Ссылка: <code>{button_url}</code>\n\n"
             f"Превью кнопки:",
        attachments=[preview_keyboard]
    )

    users_count = await db.get_active_users_count()
    await bot.send_message(
        chat_id=event.chat.id,
        text=f"📤 <b>Подтверждение рассылки</b>\n\n"
             f"👥 Получателей: <b>{users_count}</b>\n"
             f"🔗 С кнопкой: <b>Да</b>\n\n"
             f"Отправить рассылку?",
        attachments=[AdminKeyboards.broadcast_confirm(users_count)]
    )
    # Не меняем состояние – остаёмся в AdminStates.broadcast_message, так как дальше подтверждение


# ---------- Рассылка без кнопки ----------
@router.message_callback(Command('broadcast_no_button'))
async def broadcast_without_button(event: MessageCallback, context: MemoryContext) -> None:
    """
    Пользователь выбрал «Отправить без кнопки». Сразу переходим к подтверждению.
    """
    if not is_admin(event.user.user_id):
        await event.answer("❌ Нет прав")
        return

    bot = event.bot
    users_count = await db.get_active_users_count()

    await bot.update_message(
        message_id=event.message.id,
        text=f"📤 <b>Подтверждение рассылки</b>\n\n"
             f"👥 Получателей: <b>{users_count}</b>\n"
             f"🔗 С кнопкой: <b>Нет</b>\n\n"
             f"Отправить рассылку?",
        attachments=[AdminKeyboards.broadcast_confirm(users_count)]
    )
    await event.answer("")


# ---------- Подтверждение рассылки ----------
@router.message_callback(Command('broadcast_confirm_yes'))
async def confirm_broadcast(event: MessageCallback, context: MemoryContext) -> None:
    """
    Запуск рассылки.
    """
    if not is_admin(event.user.user_id):
        await event.answer("❌ Нет прав")
        return

    bot = event.bot

    # ВРЕМЕННО: просто показываем сообщение о запуске
    await bot.update_message(
        message_id=event.message.id,
        text="📤 <b>Рассылка запущена...</b> (заглушка, функционал в разработке)"
    )
    await event.answer("")
    await context.clear()


@router.message_callback(Command('broadcast_confirm_no'))
async def cancel_broadcast(event: MessageCallback, context: MemoryContext) -> None:
    """
    Отмена рассылки.
    """
    if context:
        await context.clear()
    await event.answer("")
    await event.message.edit_text(text="❌ Рассылка отменена", attachments=[])


@router.message_callback(Command('broadcast_cancel'))
async def cancel_broadcast_creation(event: MessageCallback, context: MemoryContext) -> None:
    """
    Отмена создания рассылки на любом этапе.
    """
    if context:
        await context.clear()
    await event.answer("")
    await event.message.edit_text(text="❌ Создание рассылки отменено", attachments=[])


# ---------- Команда /cancel для отмены состояния ----------
@router.message_created(Command('cancel'))
async def cancel_any_state(event: MessageCreated, context: MemoryContext) -> None:
    """
    Отмена любого текущего состояния (если есть).
    """
    if not is_admin(event.sender.user_id):
        return

    current_state = await context.get_state()
    if current_state:
        await context.clear()
        await event.message.answer(text="❌ Операция отменена")
    else:
        await event.message.answer(text="ℹ️ Нет активных операций для отмены")
