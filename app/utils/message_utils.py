from maxbot.types import Callback


async def safe_edit_message(callback: Callback, bot, text: str, **kwargs):
    """
    Безопасное редактирование сообщения для maxbot.
    Если исходное сообщение не найдено (ошибка), отправляет новое.
    """
    try:
        await bot.update_message(
            message_id=callback.message.id,
            text=text,
            **kwargs
        )
    except Exception:
        # При ошибке отправляем новое сообщение
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            **kwargs
        )
