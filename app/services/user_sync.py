"""
Сервис синхронизации пользователя с iiko.
============================================
Содержит функцию sync_user_with_iiko, которая:
- проверяет наличие номера телефона у пользователя
- получает информацию о клиенте из iiko (регистрирует, если не найден)
- выпускает карту при необходимости
- сохраняет флаг is_registered=True
- показывает главное меню

Используется в процессах регистрации и обновления legacy-пользователей.
"""

from typing import Union
import tempfile
import os

from loguru import logger

from maxapi.types import Message, MessageCallback

from app.database import db
from app.database.models import User
from app.services import iiko_service
from app.keyboards.iiko import retry_keyboard
from app.utils.qr import generate_qr_code


async def sync_user_with_iiko(
    event: Union[Message, MessageCallback],
    user: User
) -> None:
    """
    Синхронизирует данные пользователя с iiko, при необходимости регистрирует клиента,
    выпускает карту и показывает главное меню.

    Функция обрабатывает два типа событий:
    - Message (пришло из обычного сообщения)
    - MessageCallback (пришло из callback, например, после нажатия кнопки повтора)

    Для callback-события используется редактирование сообщения (bot.update_message),
    для обычного сообщения – отправка нового (bot.send_message).

    Args:
        event (Union[Message, MessageCallback]): событие, инициировавшее синхронизацию
        user (User): объект пользователя из базы данных (модель User)
    """
    # Определяем тип события и извлекаем общие данные
    if isinstance(event, MessageCallback):
        bot = event.bot
        chat_id = event.message.chat.id
        message_id = event.message.id
        is_callback = True
    else:  # Message
        bot = event.bot
        chat_id = event.chat.id
        message_id = None
        is_callback = False

    # Проверяем наличие номера телефона
    phone = str(user.phone_number) if user.phone_number else ""
    if not phone:
        text = "❌ Ошибка: номер телефона не найден."
        await bot.send_message(chat_id=chat_id, text=text)
        if is_callback:
            await event.set_state(None)  # очищаем состояние
        else:
            await event.reset_state()
        return

    card_number = None

    # 1. Пытаемся получить информацию о клиенте из iiko
    try:
        client_info = await iiko_service.get_customer_info(phone)
    except Exception as e:
        logger.error(f"Ошибка при запросе iiko для пользователя {user.id}: {e}")
        client_info = None

    # 2. Если клиент не найден – регистрируем нового
    if client_info is None:
        customer_id, reg_msg = await iiko_service.register_customer(user)
        if not customer_id:
            text = f"❌ Не удалось зарегистрировать в iiko.\nПричина: {reg_msg}"
            if is_callback:
                await bot.edit_message(
                    message_id=message_id,
                    text=text,
                    attachments=[retry_keyboard()]
                )
                await bot.answer_callback(event.callback_id, "")
            else:
                await bot.send_message(chat_id=chat_id, text=text, attachments=[retry_keyboard()])
            return
        # Клиент создан, карт пока нет
        client_info = {'customer_id': customer_id, 'cards': []}
    else:
        # 3. Клиент существует – обновляем его данные (например, если изменилось имя)
        existing_customer_id = client_info['customer_id']
        customer_id, upd_msg = await iiko_service.register_customer(user, customer_id=existing_customer_id)
        if not customer_id:
            text = f"❌ Не удалось обновить данные в iiko.\nПричина: {upd_msg}"
            if is_callback:
                await bot.edit_message(
                    message_id=message_id,
                    text=text,
                    attachments=[retry_keyboard()]
                )
                await bot.answer_callback(event.callback_id, "")
            else:
                await bot.send_message(chat_id=chat_id, text=text, attachments=[retry_keyboard()])
            return
        client_info['customer_id'] = customer_id

    # 4. Проверяем наличие карт у клиента
    cards = client_info.get('cards', [])
    if not cards:
        # Выпускаем новую карту
        success, card_msg, card_number = await iiko_service.issue_card_for_customer(str(phone),
                                                                                    client_info['customer_id'])
        if not success:
            text = f"❌ Не удалось выпустить карту.\nПричина: {card_msg}"
            if is_callback:
                await bot.edit_message(
                    message_id=message_id,
                    text=text,
                    attachments=[retry_keyboard()]
                )
                await bot.answer_callback(event.callback_id, "")
            else:
                await bot.send_message(chat_id=chat_id, text=text, attachments=[retry_keyboard()])
            return
        # После выпуска обновляем информацию о клиенте
        client_info = await iiko_service.get_customer_info(phone)
        if client_info:
            cards = client_info.get('cards', [])
        if not cards:
            cards = [{'number': card_number}]

    # 5. Успех – устанавливаем флаг регистрации
    await db.update_user(user.id, is_registered=True)

    # Если есть новая карта (и она одна), отправляем QR-код
    if len(cards) == 1 and cards[0]['number'] == card_number:
        qr_photo = await generate_qr_code(card_number)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(qr_photo)
            tmp_path = tmp.name
        await bot.send_file(
            file_path=tmp_path,
            media_type="image",
            chat_id=chat_id,
            text=f"✅ Ваша бонусная карта:\n{card_number}"
        )
        os.unlink(tmp_path)

    # Импортируем show_main_menu только здесь, чтобы избежать циклического импорта
    from app.handlers.menu import show_main_menu

    # Показываем главное меню
    await show_main_menu(
        chat_id=chat_id,
        bot=bot,
        user_name=user.first_name_input or "Гость"
    )

    # Если событие было callback, отвечаем на него (убираем "часики")
    if is_callback:
        await bot.answer_callback(event.callback_id, "")
