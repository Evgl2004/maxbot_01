"""
Сервис рассылки сообщений (адаптирован для maxbot – только текст)
"""

import asyncio
from typing import Optional, Dict

from loguru import logger

from maxbot.types import Message, InlineKeyboardMarkup

from app.database import db


class BroadcastService:
    """Сервис для рассылки сообщений (только текст и кнопки)"""

    def __init__(self, bot):
        self.bot = bot

    async def send_broadcast(
        self,
        message: Message,
        custom_keyboard: Optional[InlineKeyboardMarkup] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, int]:
        """
        Отправка рассылки всем пользователям (только текст)
        """
        users = await db.get_active_users()

        stats = {
            "total": len(users),
            "sent": 0,
            "failed": 0,
            "blocked": 0
        }

        logger.info(f"Начинаем рассылку для {len(users)} пользователей")

        batch_size = 30
        delay_between_batches = 1

        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            tasks = []

            for user in batch:
                task = self._send_single_message(
                    user_id=user.id,
                    text=message.text,
                    keyboard=custom_keyboard
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    stats["failed"] += 1
                elif result is True:
                    stats["sent"] += 1
                else:
                    stats["failed"] += 1

            if progress_callback:
                await progress_callback(stats)

            if i + batch_size < len(users):
                await asyncio.sleep(delay_between_batches)

        logger.info(f"Рассылка завершена. Отправлено: {stats['sent']}, Ошибок: {stats['failed']}, Заблокировано: {stats['blocked']}")
        return stats

    async def _send_single_message(
        self,
        user_id: int,
        text: str,
        keyboard: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Отправка одного текстового сообщения пользователю
        """
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=text or " ",
                reply_markup=keyboard,
                format="html"  # предполагаем, что исходное сообщение могло содержать HTML
            )
            return True
        except Exception as e:
            logger.debug(f"Ошибка отправки пользователю {user_id}: {e}")
            return False
