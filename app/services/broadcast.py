"""
Сервис рассылки сообщений (только текст и кнопки).
"""

import asyncio
from typing import Optional, Dict, Any

from loguru import logger

from app.database import db


class BroadcastService:
    """
    Сервис для массовой рассылки сообщений всем активным пользователям.

    Отправляет текстовые сообщения с возможностью прикрепить inline-клавиатуру.
    Работает пачками по 30 пользователей с задержкой между пачками,
    чтобы не превышать лимиты API и не создавать излишнюю нагрузку.
    """

    def __init__(self, bot):
        """
        Инициализирует сервис рассылки.

        Args:
            bot: экземпляр Bot, используемый для отправки сообщений.
        """
        self.bot = bot

    async def send_broadcast(
        self,
        text: str,
        keyboard: Optional[Any] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, int]:
        """
        Запускает рассылку сообщения всем активным пользователям.

        Аргументы:
            text (str): текст сообщения
            keyboard (Optional[Any]): inline-клавиатура (объект, который можно передать в attachments)
            progress_callback (Optional[callable]): функция, вызываемая после каждой пачки
                для обновления прогресса. Принимает словарь статистики.

        Возвращает:
            Dict[str, int]: словарь со статистикой рассылки:
                - total: всего пользователей
                - sent: успешно отправлено
                - failed: ошибки отправки
                - blocked: заблокировано (не используется в этой версии)
        """
        users = await db.get_active_users()
        total = len(users)
        stats = {"total": total, "sent": 0, "failed": 0, "blocked": 0}

        logger.info(f"Начинаем рассылку для {total} пользователей")

        batch_size = 30
        delay = 1  # задержка между пачками в секундах

        for i in range(0, total, batch_size):
            batch = users[i:i + batch_size]
            tasks = [self._send_single(user.id, text, keyboard) for user in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if res is True:
                    stats["sent"] += 1
                else:
                    stats["failed"] += 1

            if progress_callback:
                await progress_callback(stats)

            if i + batch_size < total:
                await asyncio.sleep(delay)

        logger.info(f"Рассылка завершена: {stats}")
        return stats

    async def _send_single(self, user_id: int, text: str, keyboard: Optional[Any]) -> bool:
        """
        Отправляет одно сообщение конкретному пользователю.

        Args:
            user_id (int): ID получателя.
            text (str): текст сообщения.
            keyboard (Optional[Any]): клавиатура (если есть).

        Returns:
            bool: True при успешной отправке, иначе False.
        """
        try:
            attachments = [keyboard] if keyboard else []
            await self.bot.send_message(
                chat_id=user_id,
                text=text or " ",
                attachments=attachments
            )
            return True
        except Exception as e:
            logger.debug(f"Ошибка отправки пользователю {user_id}: {e}")
            return False
