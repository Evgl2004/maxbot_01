"""
Обработчики меню Администратора
"""

import re
from loguru import logger

from maxbot.router import Router
from maxbot.types import Message, Callback
from maxbot.filters import F

from app.config import settings
from app.database import db
from app.states import AdminStates
from app.keyboards import AdminKeyboards
from app.services import BroadcastService

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    return settings.is_admin(user_id)


# ---------- Команда /admin ----------
@router.message(F.text == "/admin")
async def admin_command(message: Message):
    """Обработчик команды /admin"""
    if not is_admin(message.sender.id):
        await message.dispatcher.bot.send_message(
            chat_id=message.chat.id,
            text="❌ У вас нет прав администратора"
        )
        return

    bot = message.dispatcher.bot
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
        chat_id=message.chat.id,
        text=text,
        reply_markup=AdminKeyboards.main_admin_menu(),
        format="html"
    )


# ---------- Начало рассылки ----------
@router.callback(F.payload == "admin_broadcast")
async def start_broadcast(callback: Callback):
    """Начало создания рассылки"""
    if not is_admin(callback.user.id):
        await callback.dispatcher.bot.answer_callback(callback.callback_id, "❌ Нет прав")
        return

    await callback.set_state(AdminStates.broadcast_message)
    bot = callback.dispatcher.bot

    await bot.update_message(
        message_id=callback.message.id,
        text="📤 <b>Создание рассылки</b>\n\n"
             "Отправьте сообщение любого типа (текст, фото, видео, документ и т.д.), "
             "которое хотите разослать всем пользователям бота.\n\n"
             "Для отмены введите /cancel",
        format="html"
    )
    await bot.answer_callback(callback.callback_id, "")


# ---------- Получение сообщения для рассылки ----------
@router.message()
async def receive_broadcast_message(message: Message):
    """Получение сообщения для рассылки"""
    current_state = await message.get_state()
    if current_state != AdminStates.broadcast_message.full_name():
        return

    if not is_admin(message.sender.id):
        await message.reset_state()
        return

    bot = message.dispatcher.bot
    await message.update_data(broadcast_message=message)

    users_count = await db.get_active_users_count()
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ <b>Сообщение получено!</b>\n\n"
             f"👥 Количество получателей: <b>{users_count}</b>\n\n"
             f"Хотите добавить кнопку к сообщению?",
        reply_markup=AdminKeyboards.broadcast_add_button(),
        format="html"
    )
    await message.set_state(AdminStates.broadcast_message)  # остаёмся в том же состоянии для выбора


# ---------- Добавление кнопки ----------
@router.callback(F.payload == "broadcast_add_button")
async def add_button_to_broadcast(callback: Callback):
    """Добавление кнопки к рассылке"""
    current_state = await callback.get_state()
    if current_state != AdminStates.broadcast_message.full_name():
        return

    await callback.set_state(AdminStates.broadcast_button)
    bot = callback.dispatcher.bot

    await bot.update_message(
        message_id=callback.message.id,
        text="🔗 <b>Добавление кнопки</b>\n\n"
             "Отправьте кнопку в формате:\n"
             "<code>Текст кнопки | https://example.com</code>\n\n"
             "Пример:\n"
             "<code>Наш сайт | https://example.com</code>\n\n"
             "Для отмены введите /cancel",
        format="html"
    )
    await bot.answer_callback(callback.callback_id, "")


# ---------- Получение кнопки ----------
@router.message()
async def receive_broadcast_button(message: Message):
    """Получение кнопки для рассылки"""
    current_state = await message.get_state()
    if current_state != AdminStates.broadcast_button.full_name():
        return

    if not is_admin(message.sender.id):
        await message.reset_state()
        return

    bot = message.dispatcher.bot
    button_pattern = r"^(.+?)\s*\|\s*(https?://.+)$"
    match = re.match(button_pattern, message.text.strip())

    if not match:
        await bot.send_message(
            chat_id=message.chat.id,
            text="❌ <b>Неверный формат кнопки!</b>\n\n"
                 "Используйте формат:\n"
                 "<code>Текст кнопки | https://example.com</code>\n\n"
                 "Попробуйте еще раз или введите /cancel для отмены",
            format="html"
        )
        return

    button_text = match.group(1).strip()
    button_url = match.group(2).strip()

    await message.update_data(button_text=button_text, button_url=button_url)

    preview_keyboard = AdminKeyboards.create_custom_button(button_text, button_url)

    await bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ <b>Кнопка создана!</b>\n\n"
             f"📝 Текст: <b>{button_text}</b>\n"
             f"🔗 Ссылка: <code>{button_url}</code>\n\n"
             f"Превью кнопки:",
        reply_markup=preview_keyboard,
        format="html"
    )

    users_count = await db.get_active_users_count()
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"📤 <b>Подтверждение рассылки</b>\n\n"
             f"👥 Получателей: <b>{users_count}</b>\n"
             f"🔗 С кнопкой: <b>Да</b>\n\n"
             f"Отправить рассылку?",
        reply_markup=AdminKeyboards.broadcast_confirm(users_count),
        format="html"
    )


# ---------- Рассылка без кнопки ----------
@router.callback(F.payload == "broadcast_no_button")
async def broadcast_without_button(callback: Callback):
    """Рассылка без кнопки"""
    current_state = await callback.get_state()
    if current_state != AdminStates.broadcast_message.full_name():
        return

    users_count = await db.get_active_users_count()
    bot = callback.dispatcher.bot

    await bot.update_message(
        message_id=callback.message.id,
        text=f"📤 <b>Подтверждение рассылки</b>\n\n"
             f"👥 Получателей: <b>{users_count}</b>\n"
             f"🔗 С кнопкой: <b>Нет</b>\n\n"
             f"Отправить рассылку?",
        reply_markup=AdminKeyboards.broadcast_confirm(users_count),
        format="html"
    )
    await bot.answer_callback(callback.callback_id, "")


# ---------- Подтверждение рассылки ----------
@router.callback(F.payload == "broadcast_confirm_yes")
async def confirm_broadcast(callback: Callback):
    """Подтверждение и запуск рассылки"""
    if not is_admin(callback.user.id):
        await callback.dispatcher.bot.answer_callback(callback.callback_id, "❌ Нет прав")
        return

    data = await callback.get_data()
    broadcast_message = data.get("broadcast_message")
    if not broadcast_message:
        await callback.dispatcher.bot.update_message(
            message_id=callback.message.id,
            text="❌ Ошибка: сообщение для рассылки не найдено"
        )
        await callback.reset_state()
        return

    custom_keyboard = None
    if data.get("button_text") and data.get("button_url"):
        custom_keyboard = AdminKeyboards.create_custom_button(
            data["button_text"],
            data["button_url"]
        )

    broadcast_service = BroadcastService(callback.dispatcher.bot)

    progress_msg = await callback.dispatcher.bot.update_message(
        message_id=callback.message.id,
        text="📤 <b>Рассылка запущена...</b>\n\n"
             "📊 Прогресс: <b>0%</b>\n"
             "✅ Отправлено: <b>0</b>\n"
             "❌ Ошибок: <b>0</b>\n"
             "🚫 Заблокировано: <b>0</b>",
        format="html"
    )

    async def update_progress(stats: dict):
        progress_percent = int((stats["sent"] + stats["failed"] + stats["blocked"]) / stats["total"] * 100) if stats["total"] else 0
        try:
            await callback.dispatcher.bot.update_message(
                message_id=callback.message.id,
                text=f"📤 <b>Рассылка в процессе...</b>\n\n"
                     f"📊 Прогресс: <b>{progress_percent}%</b>\n"
                     f"✅ Отправлено: <b>{stats['sent']}</b>\n"
                     f"❌ Ошибок: <b>{stats['failed']}</b>\n"
                     f"🚫 Заблокировано: <b>{stats['blocked']}</b>",
                format="html"
            )
        except Exception:
            pass

    try:
        final_stats = await broadcast_service.send_broadcast(
            message=broadcast_message,
            custom_keyboard=custom_keyboard,
            progress_callback=update_progress
        )

        success_rate = int(final_stats["sent"] / final_stats["total"] * 100) if final_stats["total"] > 0 else 0

        await callback.dispatcher.bot.update_message(
            message_id=callback.message.id,
            text=f"✅ <b>Рассылка завершена!</b>\n\n"
                 f"📊 <b>Итоговая статистика:</b>\n"
                 f"👥 Всего получателей: <b>{final_stats['total']}</b>\n"
                 f"✅ Успешно доставлено: <b>{final_stats['sent']}</b>\n"
                 f"❌ Ошибок доставки: <b>{final_stats['failed']}</b>\n"
                 f"🚫 Заблокировали бота: <b>{final_stats['blocked']}</b>\n"
                 f"📈 Успешность: <b>{success_rate}%</b>",
            format="html"
        )

    except Exception as e:
        logger.error(f"Ошибка при рассылке: {e}")
        await callback.dispatcher.bot.update_message(
            message_id=callback.message.id,
            text=f"❌ <b>Ошибка при рассылке!</b>\n\n"
                 f"Описание: <code>{str(e)}</code>",
            format="html"
        )

    await callback.reset_state()
    await callback.dispatcher.bot.answer_callback(callback.callback_id, "")


# ---------- Отмена рассылки ----------
@router.callback(F.payload == "broadcast_confirm_no")
async def cancel_broadcast(callback: Callback):
    """Отмена рассылки"""
    await callback.reset_state()
    await callback.dispatcher.bot.update_message(
        message_id=callback.message.id,
        text="❌ Рассылка отменена"
    )
    await callback.dispatcher.bot.answer_callback(callback.callback_id, "")


@router.callback(F.payload == "broadcast_cancel")
async def cancel_broadcast_creation(callback: Callback):
    """Отмена создания рассылки"""
    await callback.reset_state()
    await callback.dispatcher.bot.update_message(
        message_id=callback.message.id,
        text="❌ Создание рассылки отменено"
    )
    await callback.dispatcher.bot.answer_callback(callback.callback_id, "")


# ---------- Команда /cancel ----------
@router.message(F.text == "/cancel")
async def cancel_any_state(message: Message):
    """Отмена любого состояния"""
    if not is_admin(message.sender.id):
        return

    current_state = await message.get_state()
    if current_state:
        await message.reset_state()
        await message.dispatcher.bot.send_message(
            chat_id=message.chat.id,
            text="❌ Операция отменена"
        )
    else:
        await message.dispatcher.bot.send_message(
            chat_id=message.chat.id,
            text="ℹ️ Нет активных операций для отмены"
        )
