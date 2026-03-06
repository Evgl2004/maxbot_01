"""
Обработчики главного меню и всех подразделов
===============================================
Содержит функции для:
- показа главного меню
- обработки пунктов главного меню (баланс, виртуальная карта, отдел заботы, вакансии)
- подменю отдела заботы (отзыв, вопрос, контакты)
- навигационных кнопок (назад в меню, назад в отдел заботы)
- создания тикетов через раздел «Мне только спросить»
"""

from loguru import logger
import tempfile
import os

from maxapi import Router
from maxapi.types import MessageCreated, MessageCallback, Command
from maxapi.context import MemoryContext

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

router = Router()


# ---------- Главное меню ----------
async def show_main_menu(chat_id: int, bot, user_name: str = "Гость") -> None:
    """
    Отправляет пользователю главное меню.

    Может вызываться из разных мест (например, после регистрации или по команде /start).

    Аргументы:
        chat_id (int): идентификатор чата, куда отправлять сообщение
        bot: экземпляр бота (для отправки сообщения)
        user_name (str): имя пользователя для приветствия
    """
    text = (
        f"👋 {user_name}, добро пожаловать!\n"
        f"Вы в главном меню.\n"
        "Выберите раздел:"
    )
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        attachments=[get_main_menu_keyboard()]
    )


# ---------- Обработчики пунктов главного меню ----------
@router.message_callback(Command('balance'))
async def process_balance(event: MessageCallback) -> None:
    """
    Показывает информацию о балансе бонусов из iiko.
    """
    bot = event.bot
    await event.answer("")

    user = await db.get_user(event.user.user_id)
    if not user or not user.phone_number:
        text = "❌ У вас не указан номер телефона. Пожалуйста, пройдите регистрацию."
        await bot.update_message(
            message_id=event.message.id,
            text=text,
            attachments=[get_back_to_main_keyboard()]
        )
        return

    client_info = await iiko_service.get_customer_info(user.phone_number)
    if client_info is None:
        text = (
            "❌ Информация о бонусах временно недоступна.\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        )
        await bot.update_message(
            message_id=event.message.id,
            text=text,
            attachments=[get_back_to_main_keyboard()]
        )
        return

    balance = client_info.get('balance', 0)
    formatted_balance = f"{balance:.2f}".replace('.', ',')

    text = (
        f"💰 *Ваш бонусный баланс*\n\n"
        f"Текущие бонусы: {formatted_balance}\n"
        f"Ближайшая дата сгорания: —\n"
        f"Количество бонусов к сгоранию: —\n"
    )
    await bot.update_message(
        message_id=event.message.id,
        text=text,
        attachments=[get_back_to_main_keyboard()]
    )


@router.message_callback(Command('virtual_card'))
async def process_virtual_card(event: MessageCallback) -> None:
    """
    Показывает все карты пользователя из iiko с QR-кодами.
    Если карт нет – выпускает автоматически.
    Если клиент не найден в iiko – регистрирует и выпускает карту.
    """
    bot = event.bot
    await event.answer("")

    user = await db.get_user(event.user.user_id)
    if not user or not user.phone_number:
        text = "❌ У вас не указан номер телефона. Пожалуйста, пройдите регистрацию через /start."
        await bot.update_message(
            message_id=event.message.id,
            text=text,
            attachments=[get_back_to_main_keyboard()]
        )
        return

    phone = user.phone_number
    client_info = await iiko_service.get_customer_info(phone)

    if client_info is None:
        customer_id, reg_msg = await iiko_service.register_customer(user)
        if not customer_id:
            text = f"❌ Не удалось зарегистрировать вас в бонусной системе.\nПричина: {reg_msg}\n\nПопробуйте позже."
            await bot.update_message(
                message_id=event.message.id,
                text=text,
                attachments=[retry_keyboard()]
            )
            return
        client_info = {'customer_id': customer_id, 'cards': []}
    else:
        if not client_info.get('customer_id'):
            customer_id, reg_msg = await iiko_service.register_customer(user)
            if not customer_id:
                text = "❌ Ошибка получения данных клиента. Попробуйте позже."
                await bot.update_message(
                    message_id=event.message.id,
                    text=text,
                    attachments=[retry_keyboard()]
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
                message_id=event.message.id,
                text=text,
                attachments=[retry_keyboard()]
            )
            return
        client_info = await iiko_service.get_customer_info(phone)
        if not client_info:
            cards = [{'number': card_number}]
        else:
            cards = client_info.get('cards', [])
            if not cards:
                cards = [{'number': card_number}]

    await bot.delete_message(event.message.id)

    for card in cards:
        card_number = card['number']
        qr_photo = await generate_qr_code(card_number)

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(qr_photo)
            tmp_path = tmp.name

        caption = f"💳 Карта: {card_number}"
        if card.get('valid_to'):
            caption += f"\nДействует до: {card['valid_to']}"

        await bot.send_file(
            file_path=tmp_path,
            media_type="image",
            chat_id=event.message.chat.id,
            text=caption
        )

        os.unlink(tmp_path)

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
        chat_id=event.message.chat.id,
        text=final_text,
        attachments=[get_back_to_main_keyboard()]
    )


@router.message_callback(Command('support'))
async def process_support(event: MessageCallback) -> None:
    """
    Показывает вложенное меню отдела заботы с учётом наличия тикетов у пользователя.
    """
    bot = event.bot
    await event.answer("")

    user_id = event.user.user_id
    tickets_count = await ticket_service.get_user_tickets_count(user_id)
    has_tickets = tickets_count > 0

    text = "🆘 *Отдел заботы*\n\nВыберите действие:"
    await bot.update_message(
        message_id=event.message.id,
        text=text,
        attachments=[get_support_submenu_keyboard(has_tickets=has_tickets)]
    )


@router.message_callback(Command('vacancies'))
async def process_vacancies(event: MessageCallback) -> None:
    """
    Показывает информацию о вакансиях и ссылку.
    """
    bot = event.bot
    await event.answer("")

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
        message_id=event.message.id,
        text=text,
        attachments=[get_back_to_main_keyboard()]
    )


# ---------- Обработчики подменю отдела заботы ----------
@router.message_callback(Command('support_feedback'))
async def process_feedback(event: MessageCallback) -> None:
    """
    Отправляет ссылку на внешний сервис отзывов.
    """
    bot = event.bot
    await event.answer("")

    text = (
        "✍️ *Оставить отзыв*\n\n"
        "Мы будем рады узнать ваше мнение! Перейдите по ссылке ниже:\n"
        "👉 [Форма обратной связи](https://example.com/feedback) (ссылка будет заменена)"
    )
    await bot.update_message(
        message_id=event.message.id,
        text=text,
        attachments=[get_back_to_support_keyboard()]
    )


@router.message_callback(Command('support_question'))
async def process_question(event: MessageCallback, context: MemoryContext) -> None:
    """
    Обработчик функции 'Мне только спросить' – начало создания тикета.
    Устанавливает состояние ожидания вопроса и просит пользователя ввести текст.
    """
    bot = event.bot
    await event.answer("")
    await context.set_state(TicketStates.waiting_for_question)

    text = (
        "❓ *Мне только спросить*\n\n"
        "Пожалуйста, отправьте ваш вопрос, и наш модератор свяжется с вами в ближайшее время.\n\n"
        "Введите ваш вопрос:"
    )
    await bot.update_message(
        message_id=event.message.id,
        text=text,
        attachments=[get_back_to_support_keyboard()]
    )


@router.message_created(TicketStates.waiting_for_question)
async def process_question_text(event: MessageCreated, context: MemoryContext) -> None:
    """
    Обработчик текста вопроса от пользователя.
    Создаёт тикет, уведомляет модераторов и очищает состояние.
    """
    bot = event.bot

    if not event.message.text:
        await bot.send_message(
            chat_id=event.chat.id,
            text="✍️ Пожалуйста, введите вопрос текстовым сообщением."
        )
        return

    user = await db.get_user(event.sender.user_id)
    if not user:
        await bot.send_message(chat_id=event.chat.id, text="❌ Ошибка: пользователь не найден")
        await context.clear()
        return

    ticket = await ticket_service.create_ticket(
        user_id=event.sender.user_id,
        message=event.message.text,
        user_username=event.sender.name,
        user_first_name=event.sender.first_name or user.first_name_input
    )

    await bot.send_message(
        chat_id=event.chat.id,
        text=(
            f"📨 Ваш вопрос принят!\n\n"
            f"🎫 Создан тикет #{ticket.id}\n"
            f"🕐 Модератор рассмотрит ваш вопрос в ближайшее время.\n\n"
            f"Вы получите уведомление с ответом."
        )
    )

    try:
        open_count, in_progress_count, avg_response_time = await ticket_service.get_tickets_stats()
        notification_text = (
            f"📬 *Новый тикет от пользователя!*\n\n"
            f"🎫 Тикет #{ticket.id}\n"
            f"👤 Пользователь: {event.sender.name or event.sender.first_name}\n"
            f"❓ Вопрос: {event.message.text[:100]}{'...' if len(event.message.text) > 100 else ''}\n\n"
            f"📊 *Статистика:*\n"
            f"📬 Новые тикеты: {open_count}\n"
            f"🔄 В работе: {in_progress_count}\n"
        )
        moderators = await db.get_moderators()
        for moderator in moderators:
            try:
                await bot.send_message(
                    chat_id=moderator.id,
                    text=notification_text,
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления модератору {moderator.id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления модераторам: {e}")

    await context.clear()


@router.message_callback(Command('support_contacts'))
async def process_contacts(event: MessageCallback) -> None:
    """
    Показывает контактную информацию.
    """
    bot = event.bot
    await event.answer("")

    text = (
        "📧 Контакты:\n\n"
        "Почта для связи: info@sobolev.rest\n"
        "Сайт: https://sobolevalliance.su\n"
        "Соцсети: @sobolevalliance"
    )
    await bot.update_message(
        message_id=event.message.id,
        text=text,
        attachments=[get_back_to_support_keyboard()]
    )


# ---------- Навигационные кнопки ----------
@router.message_callback(Command('back_to_main'))
async def process_back_to_main(event: MessageCallback, context: MemoryContext) -> None:
    """
    Возврат в главное меню.
    Удаляет текущее сообщение и отправляет новое с главным меню.
    """
    if context:
        await context.clear()

    bot = event.bot
    await event.answer("")

    user = await db.get_user(event.user.user_id)
    if not user:
        await bot.answer_callback(event.callback_id, "Пользователь не найден")
        return

    name = user.first_name_input or "Гость"
    text = f"👋 {name}, вы в главном меню.\nВыберите раздел:"
    await bot.delete_message(event.message.id)
    await bot.send_message(
        chat_id=event.message.chat.id,
        text=text,
        attachments=[get_main_menu_keyboard()]
    )


@router.message_callback(Command('back_to_support'))
async def process_back_to_support(event: MessageCallback, context: MemoryContext) -> None:
    """
    Возврат во вложенное меню отдела заботы.
    """
    if context:
        await context.clear()

    bot = event.bot
    await event.answer("")

    user_id = event.user.user_id
    tickets_count = await ticket_service.get_user_tickets_count(user_id)
    has_tickets = tickets_count > 0

    text = "🆘 *Отдел заботы*\n\nВыберите действие:"
    await bot.update_message(
        message_id=event.message.id,
        text=text,
        attachments=[get_support_submenu_keyboard(has_tickets=has_tickets)]
    )
