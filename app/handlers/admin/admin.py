"""
Обработчики меню Администратора
=================================
Содержит функции для:
- команды /admin
- начала создания рассылки
- приёма сообщения для рассылки
- добавления кнопки
- подтверждения рассылки
- запуска рассылки через сервис BroadcastService (временно заглушка)
- команды /cancel для отмены текущего состояния

Все хендлеры используют корректные методы maxapi:
- Текст сообщения: event.message.body.text
- Редактирование: event.bot.edit_message с обязательным message_id
- Отправка клавиатур: attachments=[keyboard]
- Работа с FSM: context (MemoryContext) передаётся вторым параметром
- Ответ на callback: await event.answer("")
- Отправка простых сообщений: bot.send_message
"""

import re

from maxapi import Router
from maxapi.types import MessageCreated, MessageCallback, Command
from maxapi.context import MemoryContext
from maxapi.enums.parse_mode import ParseMode
from maxapi import F

from app.config import settings
from app.database import db
from app.states import AdminStates
from app.keyboards import AdminKeyboards

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором.

    Args:
        user_id (int): ID пользователя.

    Returns:
        bool: True, если пользователь есть в списке ADMIN_USER_IDS.
    """
    return settings.is_admin(user_id)


# ---------- Команда /admin ----------
@router.message_created(Command('admin'))
async def admin_command(event: MessageCreated) -> None:
    """
    Обработчик команды /admin. Показывает статистику и главное меню администратора.

    Если пользователь не админ, выводит сообщение об ошибке.
    Статистика берётся из БД (таблица bot_stats).

    Args:
        event (MessageCreated): событие создания сообщения.
    """
    if not is_admin(event.from_user.user_id):
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
        chat_id=event.chat.chat_id,
        text=text,
        attachments=[AdminKeyboards.main_admin_menu()],
        parse_mode=ParseMode.HTML
    )


# ---------- Начало создания рассылки ----------
@router.message_callback(F.callback.payload == 'admin_broadcast')
async def start_broadcast(event: MessageCallback, context: MemoryContext) -> None:
    """
    Нажатие на кнопку «Рассылка» – переход к вводу сообщения.

    Устанавливает состояние AdminStates.broadcast_message и просит
    администратора отправить сообщение для рассылки.

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку
        context (MemoryContext): контекст FSM для установки состояния
    """
    if not is_admin(event.from_user.user_id):
        await event.answer("❌ Нет прав")
        return

    bot = event.bot
    await context.set_state(AdminStates.broadcast_message)

    await bot.edit_message(
        message_id=event.message.body.mid,
        text="📤 <b>Создание рассылки</b>\n\n"
             "Отправьте сообщение любого типа (текст, фото, видео, документ и т.д.), "
             "которое хотите разослать всем пользователям бота.\n\n"
             "Для отмены введите /cancel",
        parse_mode=ParseMode.HTML
    )
    await event.answer("")


# ---------- Получение сообщения для рассылки ----------
@router.message_created(AdminStates.broadcast_message)
async def receive_broadcast_message(event: MessageCreated, context: MemoryContext) -> None:
    """
    Получение сообщения, которое будет разослано.

    Сохраняет факт получения сообщения в контексте (пока без сохранения самого сообщения)
    и предлагает добавить кнопку или отправить без кнопки.

    Args:
        event (MessageCreated): событие создания сообщения
        context (MemoryContext): контекст FSM для сохранения данных и управления состоянием
    """
    if not is_admin(event.from_user.user_id):
        await context.clear()
        return

    bot = event.bot
    # Запоминаем, что сообщение получено (само сообщение будем передавать в BroadcastService позже)
    await context.update_data(broadcast_message_received=True)

    users_count = await db.get_active_users_count()
    await bot.send_message(
        chat_id=event.chat.chat_id,
        text=f"✅ <b>Сообщение получено!</b>\n\n"
             f"👥 Количество получателей: <b>{users_count}</b>\n\n"
             f"Хотите добавить кнопку к сообщению?",
        attachments=[AdminKeyboards.broadcast_add_button()],
        parse_mode=ParseMode.HTML
    )
    # Остаёмся в том же состоянии для выбора (AdminStates.broadcast_message)
    await context.set_state(AdminStates.broadcast_message)


# ---------- Добавление кнопки ----------
@router.message_callback(F.callback.payload == 'broadcast_add_button')
async def add_button_to_broadcast(event: MessageCallback, context: MemoryContext) -> None:
    """
    Пользователь выбрал «Добавить кнопку». Переходим к вводу данных кнопки.

    Устанавливает состояние AdminStates.broadcast_button и просит ввести
    кнопку в формате "Текст | URL".

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку
        context (MemoryContext): контекст FSM для установки состояния
    """
    if not is_admin(event.from_user.user_id):
        await event.answer("❌ Нет прав")
        return

    bot = event.bot
    await context.set_state(AdminStates.broadcast_button)

    await bot.edit_message(
        message_id=event.message.body.mid,
        text="🔗 <b>Добавление кнопки</b>\n\n"
             "Отправьте кнопку в формате:\n"
             "<code>Текст кнопки | https://example.com</code>\n\n"
             "Пример:\n"
             "<code>Наш сайт | https://example.com</code>\n\n"
             "Для отмены введите /cancel",
        parse_mode=ParseMode.HTML
    )
    await event.answer("")


# ---------- Получение данных кнопки ----------
@router.message_created(AdminStates.broadcast_button)
async def receive_broadcast_button(event: MessageCreated, context: MemoryContext) -> None:
    """
    Обрабатывает ввод кнопки (текст и URL).

    Проверяет формат "Текст | URL", сохраняет данные в контексте,
    показывает превью кнопки и переходит к подтверждению рассылки.

    Args:
        event (MessageCreated): событие создания сообщения
        context (MemoryContext): контекст FSM для сохранения данных
    """
    if not is_admin(event.from_user.user_id):
        await context.clear()
        return

    bot = event.bot
    if not event.message.body.text:
        await bot.send_message(
            chat_id=event.chat.chat_id,
            text="✍️ Пожалуйста, отправьте текстовое сообщение."
        )
        return

    button_pattern = r"^(.+?)\s*\|\s*(https?://.+)$"
    match = re.match(button_pattern, event.message.body.text.strip())

    if not match:
        await bot.send_message(
            chat_id=event.chat.chat_id,
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
        chat_id=event.chat.chat_id,
        text=f"✅ <b>Кнопка создана!</b>\n\n"
             f"📝 Текст: <b>{button_text}</b>\n"
             f"🔗 Ссылка: <code>{button_url}</code>\n\n"
             f"Превью кнопки:",
        attachments=[preview_keyboard],
        parse_mode=ParseMode.HTML
    )

    users_count = await db.get_active_users_count()
    await bot.send_message(
        chat_id=event.chat.chat_id,
        text=f"📤 <b>Подтверждение рассылки</b>\n\n"
             f"👥 Получателей: <b>{users_count}</b>\n"
             f"🔗 С кнопкой: <b>Да</b>\n\n"
             f"Отправить рассылку?",
        attachments=[AdminKeyboards.broadcast_confirm(users_count)]
    )
    # Не меняем состояние – остаёмся в AdminStates.broadcast_message, так как дальше подтверждение


# ---------- Рассылка без кнопки ----------
@router.message_callback(F.callback.payload == 'broadcast_no_button')
async def broadcast_without_button(event: MessageCallback) -> None:
    """
    Пользователь выбрал «Отправить без кнопки». Сразу переходим к подтверждению.

    Показывает окно подтверждения с количеством получателей.

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку
    """
    if not is_admin(event.from_user.user_id):
        await event.answer("❌ Нет прав")
        return

    bot = event.bot
    users_count = await db.get_active_users_count()

    await bot.edit_message(
        message_id=event.message.body.mid,
        text=f"📤 <b>Подтверждение рассылки</b>\n\n"
             f"👥 Получателей: <b>{users_count}</b>\n"
             f"🔗 С кнопкой: <b>Нет</b>\n\n"
             f"Отправить рассылку?",
        attachments=[AdminKeyboards.broadcast_confirm(users_count)],
        parse_mode=ParseMode.HTML
    )
    await event.answer("")


# ---------- Подтверждение рассылки ----------
@router.message_callback(F.callback.payload == 'broadcast_confirm_yes')
async def confirm_broadcast(event: MessageCallback, context: MemoryContext) -> None:
    """
    Запуск рассылки (временно – заглушка).

    В будущем здесь будет вызываться BroadcastService.
    Сейчас просто показывает сообщение о запуске и очищает контекст.

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку
        context (MemoryContext): контекст FSM для очистки
    """
    if not is_admin(event.from_user.user_id):
        await event.answer("❌ Нет прав")
        return

    bot = event.bot

    # ВРЕМЕННО: просто показываем сообщение о запуске
    await bot.edit_message(
        message_id=event.message.body.mid,
        text="📤 <b>Рассылка запущена...</b> (заглушка, функционал в разработке)",
        parse_mode=ParseMode.HTML
    )
    await event.answer("")
    await context.clear()


@router.message_callback(F.callback.payload == 'broadcast_confirm_no')
async def cancel_broadcast(event: MessageCallback, context: MemoryContext) -> None:
    """
    Отмена рассылки.

    Очищает контекст и заменяет сообщение на «❌ Рассылка отменена».

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку.
        context (MemoryContext): контекст FSM для очистки.
    """
    if context:
        await context.clear()
    await event.answer("")
    await event.bot.edit_message(
        message_id=event.message.body.mid,
        text="❌ Рассылка отменена",
        attachments=[]
    )


@router.message_callback(F.callback.payload == 'broadcast_cancel')
async def cancel_broadcast_creation(event: MessageCallback, context: MemoryContext) -> None:
    """
    Отмена создания рассылки на любом этапе.

    Очищает контекст и заменяет сообщение на «❌ Создание рассылки отменено».

    Args:
        event (MessageCallback): событие нажатия на callback-кнопку
        context (MemoryContext): контекст FSM для очистки
    """
    if context:
        await context.clear()
    await event.answer("")
    await event.bot.edit_message(
        message_id=event.message.body.mid,
        text="❌ Создание рассылки отменено",
        attachments=[]
    )


# ---------- Команда /cancel для отмены состояния ----------
@router.message_created(Command('cancel'))
async def cancel_any_state(event: MessageCreated, context: MemoryContext) -> None:
    """
    Отмена любого текущего состояния (если есть).

    Если пользователь находится в каком-либо состоянии FSM, оно очищается.
    Иначе выводится информационное сообщение.

    Args:
        event (MessageCreated): событие создания сообщения
        context (MemoryContext): контекст FSM для проверки и очистки состояния
    """
    if not is_admin(event.from_user.user_id):
        return

    current_state = await context.get_state()
    if current_state:
        await context.clear()
        await event.message.answer(text="❌ Операция отменена")
    else:
        await event.message.answer(text="ℹ️ Нет активных операций для отмены")
