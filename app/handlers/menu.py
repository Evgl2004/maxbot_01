"""
Обработчики главного меню и всех подразделов.
"""

from loguru import logger
import tempfile
import os

from maxbot.router import Router
from maxbot.types import Message, Callback
from maxbot.filters import F
from maxbot.bot import Bot

from app.database import db
from app.services.tickets import ticket_service
from app.keyboards.menu import (
    get_main_menu_keyboard,
    get_support_submenu_keyboard,
    get_back_to_main_keyboard,
    get_back_to_support_keyboard,
)
from app.states.tickets import TicketStates
from app.services import iiko_service
from app.keyboards.iiko import retry_keyboard
from app.utils.qr import generate_qr_code
from app.utils.validation import confirm_text
from app.utils import with_logging, with_user_save

router = Router()


# ---------- Главное меню ----------
async def show_main_menu(chat_id: int, bot: Bot, user_name: str = "Гость"):
    """
    Отправляет пользователю главное меню.
    Может вызываться из разных мест (например, после регистрации или по команде /start).
    """
    text = (
        f"👋 {user_name}, добро пожаловать!\n"
        f"Вы в главном меню.\n"
        "Выберите раздел:"
    )
    await bot.send_message(int(chat_id), text, reply_markup=get_main_menu_keyboard())


# ---------- Обработчики пунктов главного меню ----------
@router.callback(F.payload == "balance")
async def process_balance(callback: Callback):
    """Показывает информацию о балансе бонусов из iiko."""
    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")

    user = await db.get_user(callback.user.id)
    if not user or not user.phone_number:
        text = "❌ У вас не указан номер телефона. Пожалуйста, пройдите регистрацию."
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            reply_markup=get_back_to_main_keyboard()
        )
        return

    client_info = await iiko_service.get_customer_info(user.phone_number)
    if client_info is None:
        text = (
            "❌ Информация о бонусах временно недоступна.\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        )
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            reply_markup=get_back_to_main_keyboard()
        )
        return

    balance = client_info.get('balance', 0)
    formatted_balance = f"{balance:.2f}".replace('.', ',')
    expiration_date = "—"
    expiring_bonuses = "—"

    text = (
        f"💰 *Ваш бонусный баланс*\n\n"
        f"Текущие бонусы: {formatted_balance}\n"
        f"Ближайшая дата сгорания: {expiration_date}\n"
        f"Количество бонусов к сгоранию: {expiring_bonuses}\n"
    )
    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=get_back_to_main_keyboard(),
        format="markdown"
    )


@router.callback(F.payload == "virtual_card")
async def process_virtual_card(callback: Callback):
    """
    Показывает все карты пользователя из iiko с QR-кодами.
    Если карт нет – выпускает автоматически.
    Если клиент не найден в iiko – регистрирует и выпускает карту.
    """
    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")

    user = await db.get_user(callback.user.id)
    if not user or not user.phone_number:
        text = "❌ У вас не указан номер телефона. Пожалуйста, пройдите регистрацию через /start"
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            reply_markup=get_back_to_main_keyboard()
        )
        return

    phone = user.phone_number
    client_info = await iiko_service.get_customer_info(phone)

    if client_info is None:
        customer_id, reg_msg = await iiko_service.register_customer(user)
        if not customer_id:
            text = f"❌ Не удалось зарегистрировать вас в бонусной системе.\nПричина: {reg_msg}\n\nПопробуйте позже."
            await bot.update_message(
                message_id=callback.message.id,
                text=text,
                reply_markup=retry_keyboard()
            )
            return
        client_info = {'customer_id': customer_id, 'cards': []}
    else:
        if not client_info.get('customer_id'):
            customer_id, reg_msg = await iiko_service.register_customer(user)
            if not customer_id:
                text = f"❌ Ошибка получения данных клиента. Попробуйте позже."
                await bot.update_message(
                    message_id=callback.message.id,
                    text=text,
                    reply_markup=retry_keyboard()
                )
                return
            client_info['customer_id'] = customer_id

    customer_id = client_info['customer_id']
    cards = client_info.get('cards', [])

    if not cards:
        success, msg, card_number = await iiko_service.issue_card_for_customer(phone, customer_id)
        if not success:
            text = f"❌ Не удалось выпустить карту.\nПричина: {msg}\n\nПопробуйте позже."
            await bot.update_message(
                message_id=callback.message.id,
                text=text,
                reply_markup=retry_keyboard()
            )
            return
        client_info = await iiko_service.get_customer_info(phone)
        if not client_info:
            cards = [{'number': card_number}]
        else:
            cards = client_info.get('cards', [])
            if not cards:
                cards = [{'number': card_number}]

    # Удаляем предыдущее сообщение
    await bot.delete_message(callback.message.id)

    # Отправляем QR-коды для каждой карты
    for card in cards:
        card_number = card['number']
        qr_photo = await generate_qr_code(card_number)

        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(qr_photo)  # ожидаем, что qr_photo это bytes
            tmp_path = tmp.name

        # Загружаем файл в MAX
        token = await bot.upload_file(tmp_path, "image")

        caption = f"💳 Карта: {card_number}"
        if card.get('valid_to'):
            caption += f"\nДействует до: {card['valid_to']}"

        # Отправляем изображение
        await bot.send_file(
            file_path=tmp_path,
            media_type="image",
            chat_id=callback.message.chat.id,
            text=caption
        )

        # Удаляем временный файл
        os.unlink(tmp_path)

    # Итоговое сообщение
    card_count = len(cards)
    if card_count == 1:
        ending = "карта"
    elif 1 < card_count < 5:
        ending = "карты"
    else:
        ending = "карт"

    final_text = (
        f"✅ Это все ваши бонусные {ending} ({card_count} шт.).\n"
        "Вы можете показать любой QR-код официанту для начисления бонусов.\n\n"
        "*Данная программа лояльности не распространяется на УСЛУГИ ДОСТАВКИ, "
        "столовые 'Ассорти', мастерскую сыра «Страчателли»*"
    )
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=final_text,
        reply_markup=get_back_to_main_keyboard(),
        format="markdown"
    )


@router.callback(F.payload == "support")
async def process_support(callback: Callback):
    """Показывает вложенное меню отдела заботы с учётом наличия тикетов"""
    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")

    user_id = callback.user.id
    tickets_count = await ticket_service.get_user_tickets_count(user_id)
    has_tickets = tickets_count > 0

    text = "🆘 *Отдел заботы*\n\nВыберите действие:"

    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=get_support_submenu_keyboard(has_tickets=has_tickets),
        format="markdown"
    )


@router.callback(F.payload == "vacancies")
async def process_vacancies(callback: Callback):
    """Показывает информацию о вакансиях и ссылку."""
    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")

    text = (
        "💼 *Вакансии*\n\n"
        "Ждем классных, ответственных, позитивных, энергичных и профессиональных "
        "сотрудников в дружные команды наших заведений!\n\n"
        "Гарантируем:\n"
        "• крепкие коллективы, в которых весело работать и приятно отдыхать после смены\n"
        "• с нами – непрерывное профессиональное развитие\n"
        "• мы не дадим скучать и хандрить\n"
        "• достойный доход и щедрые чаевые\n\n"
        "Если чувствуешь, что хочешь работать в заведениях самого уютного и надёжного "
        "бренда Тюмени – переходи по ссылке и оставляй заявку!\n\n"
        "👉 [Посмотреть все вакансии](https://team.sobolevalliance.su/vacancy)"
    )

    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=get_back_to_main_keyboard(),
        format="markdown"
        # disable_web_page_preview отсутствует в maxbot, но можно игнорировать
    )


# ---------- Обработчики подменю отдела заботы ----------
@router.callback(F.payload == "support_feedback")
async def process_feedback(callback: Callback):
    """Отправляет ссылку на внешний сервис отзывов."""
    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")

    text = (
        "✍️ *Оставить отзыв*\n\n"
        "Мы будем рады узнать ваше мнение! Перейдите по ссылке ниже:\n"
        "👉 [Форма обратной связи](https://example.com/feedback) (ссылка будет заменена)"
    )

    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=get_back_to_support_keyboard(),
        format="markdown"
    )


@router.callback(F.payload == "support_question")
async def process_question(callback: Callback):
    """Обработчик функции 'Мне только спросить' - создание тикета."""
    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")
    await callback.set_state(TicketStates.waiting_for_question)

    text = (
        "❓ *Мне только спросить*\n\n"
        "Пожалуйста, отправьте ваш вопрос, и наш модератор свяжется с вами в ближайшее время.\n\n"
        "Введите ваш вопрос:"
    )

    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=get_back_to_support_keyboard(),
        format="markdown"
    )


@router.message()
async def process_question_text(message: Message):
    """Обработчик текста вопроса от пользователя."""

    current_state = await message.get_state()
    if current_state != TicketStates.waiting_for_question.full_name():
        return

    if not message.text:
        await message.dispatcher.bot.send_message(
            chat_id=message.chat.id,
            text="✍️ Пожалуйста, введите вопрос текстовым сообщением."
        )
        return

    user = await db.get_user(message.sender.id)
    if not user:
        await message.dispatcher.bot.send_message(chat_id=message.chat.id, text="❌ Ошибка: пользователь не найден")
        await message.reset_state()
        return

    ticket = await ticket_service.create_ticket(
        user_id=message.sender.id,
        message=message.text,
        user_username=message.sender.username,
        user_first_name=message.sender.first_name or user.first_name_input
    )

    await message.dispatcher.bot.send_message(
        chat_id=message.chat.id,
        text=(
            f"📨 Ваш вопрос принят!\n\n"
            f"🎫 Создан тикет #{ticket.id}\n"
            f"🕐 Модератор рассмотрит ваш вопрос в ближайшее время.\n\n"
            f"Вы получите уведомление с ответом."
        )
    )

    # Уведомление модераторам
    try:
        open_count, in_progress_count, avg_response_time = await ticket_service.get_tickets_stats()
        notification_text = (
            f"📬 *Новый тикет от пользователя!*\n\n"
            f"🎫 Тикет #{ticket.id}\n"
            f"👤 Пользователь: {message.sender.username or message.sender.first_name}\n"
            f"❓ Вопрос: {message.text[:100]}{'...' if len(message.text) > 100 else ''}\n\n"
            f"📊 *Статистика:*\n"
            f"📬 Новые тикеты: {open_count}\n"
            f"🔄 В работе: {in_progress_count}\n"
        )
        moderators = await db.get_moderators()
        for moderator in moderators:
            try:
                await message.dispatcher.bot.send_message(
                    chat_id=moderator.id,
                    text=notification_text,
                    format="markdown"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления модератору {moderator.id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления модераторам: {e}")

    await message.reset_state()


@router.callback(F.payload == "support_contacts")
async def process_contacts(callback: Callback):
    """Показывает контактную информацию."""
    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")

    text = (
        "📧 Контакты:\n\n"
        "Почта для связи: info@sobolev.rest\n"
        "Сайт: https://sobolevalliance.su\n"
        "Соцсети: @sobolevalliance"
    )

    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=get_back_to_support_keyboard()
    )


# ---------- Навигационные кнопки ----------
@router.callback(F.payload == "back_to_main")
async def process_back_to_main(callback: Callback):
    """Возврат в главное меню."""
    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")
    await callback.reset_state()

    user = await db.get_user(callback.user.id)
    if not user:
        await bot.answer_callback(callback.callback_id, "Пользователь не найден")
        return

    name = user.first_name_input or "Гость"
    text = f"👋 {name}, вы в главном меню.\nВыберите раздел:"
    await bot.delete_message(callback.message.id)
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=get_main_menu_keyboard()
    )


@router.callback(F.payload == "back_to_support")
async def process_back_to_support(callback: Callback):
    """Возврат во вложенный отдел заботы."""
    bot = callback.dispatcher.bot
    await bot.answer_callback(callback.callback_id, "")
    await callback.reset_state()

    user_id = callback.user.id
    tickets_count = await ticket_service.get_user_tickets_count(user_id)
    has_tickets = tickets_count > 0

    text = "🆘 *Отдел заботы*\n\nВыберите действие:"

    await bot.update_message(
        message_id=callback.message.id,
        text=text,
        reply_markup=get_support_submenu_keyboard(has_tickets=has_tickets),
        format="markdown"
    )
