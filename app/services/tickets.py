"""
Сервис для работы с тикетами системы модерации.
==================================================
Предоставляет методы для создания, получения, обновления тикетов,
а также для работы с сообщениями внутри тикетов.
"""

from typing import List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import select, func, text

from app.database.models import Ticket, TicketMessage
from app.database import db

from loguru import logger


class TicketService:
    """Сервис для работы с тикетами."""

    @staticmethod
    async def create_ticket(
        user_id: int,
        message: str,
        user_username: Optional[str] = None,
        user_first_name: Optional[str] = None
    ) -> Ticket:
        """
        Создаёт новый тикет.

        Args:
            user_id (int): ID пользователя, создающего тикет.
            message (str): текст вопроса.
            user_username (Optional[str]): username пользователя (если есть).
            user_first_name (Optional[str]): имя пользователя (если есть).

        Returns:
            Ticket: созданный объект тикета.
        """
        async with db.session_maker() as session:
            ticket = Ticket(
                user_id=user_id,
                message=message,
                user_username=user_username,
                user_first_name=user_first_name
            )
            session.add(ticket)
            await session.commit()
            await session.refresh(ticket)
            return ticket

    @staticmethod
    async def get_ticket(ticket_id: int) -> Optional[Ticket]:
        """
        Получает тикет по его ID.

        Args:
            ticket_id (int): ID тикета.

        Returns:
            Optional[Ticket]: объект тикета или None, если не найден.
        """
        async with db.session_maker() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def get_user_tickets(user_id: int) -> List[Ticket]:
        """
        Получает все тикеты пользователя (отсортированы по убыванию даты создания).

        Args:
            user_id (int): ID пользователя.

        Returns:
            List[Ticket]: список тикетов.
        """
        async with db.session_maker() as session:
            result = await session.execute(
                select(Ticket)
                .where(Ticket.user_id == user_id)
                .order_by(Ticket.created_at.desc())
            )
            return result.scalars().all()

    @staticmethod
    async def get_all_tickets(statuses: Optional[List[str]] = None) -> List[Ticket]:
        """
        Получает все тикеты, опционально фильтруя по статусам.

        Args:
            statuses (Optional[List[str]]): список статусов для фильтрации (например, ['open', 'in_progress']).

        Returns:
            List[Ticket]: список тикетов.
        """
        async with db.session_maker() as session:
            query = select(Ticket)
            if statuses:
                query = query.where(Ticket.status.in_(statuses))
            query = query.order_by(Ticket.created_at.desc())
            result = await session.execute(query)
            return result.scalars().all()

    @staticmethod
    async def get_tickets_stats() -> Tuple[int, int, Optional[float]]:
        """
        Возвращает статистику по тикетам.

        Returns:
            Tuple[int, int, Optional[float]]:
                - количество открытых тикетов
                - количество тикетов в работе
                - среднее время первого ответа (в минутах) или None, если нет данных
        """
        async with db.session_maker() as session:
            # Количество открытых тикетов
            open_count_result = await session.execute(
                select(func.count(Ticket.id))
                .where(Ticket.status == 'open')
            )
            open_count = open_count_result.scalar() or 0

            # Количество тикетов в работе
            in_progress_count_result = await session.execute(
                select(func.count(Ticket.id))
                .where(Ticket.status == 'in_progress')
            )
            in_progress_count = in_progress_count_result.scalar() or 0

            # Среднее время ответа (в минутах)
            avg_response_time = None
            avg_response_result = await session.execute(text("""
                SELECT AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 60) 
                FROM tickets 
                WHERE first_response_at IS NOT NULL
            """))
            avg_response_row = avg_response_result.fetchone()
            if avg_response_row and avg_response_row[0] is not None:
                avg_response_time = round(float(avg_response_row[0]), 1)

            return open_count, in_progress_count, avg_response_time

    @staticmethod
    async def update_ticket_status(ticket_id: int, status: str) -> bool:
        """
        Обновляет статус тикета.

        Args:
            ticket_id (int): ID тикета.
            status (str): новый статус ('open', 'in_progress', 'closed').

        Returns:
            bool: True, если обновление успешно, False если тикет не найден.
        """
        async with db.session_maker() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                return False

            # Если статус меняется на in_progress и это первый ответ
            if status == 'in_progress' and ticket.status == 'open':
                ticket.first_response_at = datetime.now(timezone.utc)

            # Если статус меняется на closed (и ранее не был закрыт)
            if status == 'closed' and ticket.status != 'closed':
                ticket.closed_at = datetime.now(timezone.utc)

            ticket.status = status
            ticket.updated_at = datetime.now(timezone.utc)
            await session.commit()
            return True

    @staticmethod
    async def close_ticket(ticket_id: int) -> bool:
        """
        Закрывает тикет (устанавливает статус 'closed').

        Args:
            ticket_id (int): ID тикета.

        Returns:
            bool: True, если операция успешна.
        """
        return await TicketService.update_ticket_status(ticket_id, 'closed')

    @staticmethod
    async def add_message_to_ticket(
        ticket_id: int,
        sender_type: str,
        sender_id: int,
        message: str
    ) -> TicketMessage:
        """
        Добавляет сообщение в тикет.

        Args:
            ticket_id (int): ID тикета.
            sender_type (str): тип отправителя ('user' или 'moderator').
            sender_id (int): ID отправителя.
            message (str): текст сообщения.

        Returns:
            TicketMessage: созданный объект сообщения.
        """
        async with db.session_maker() as session:
            ticket_message = TicketMessage(
                ticket_id=ticket_id,
                sender_type=sender_type,
                sender_id=sender_id,
                message=message
            )
            session.add(ticket_message)
            await session.commit()
            await session.refresh(ticket_message)
            return ticket_message

    @staticmethod
    async def get_ticket_messages(ticket_id: int) -> List[TicketMessage]:
        """
        Получает все сообщения тикета в порядке возрастания времени создания.

        Args:
            ticket_id (int): ID тикета.

        Returns:
            List[TicketMessage]: список сообщений.
        """
        async with db.session_maker() as session:
            result = await session.execute(
                select(TicketMessage)
                .where(TicketMessage.ticket_id == ticket_id)
                .order_by(TicketMessage.created_at.asc())
            )
            return result.scalars().all()

    @staticmethod
    async def get_tickets_page(
        page: int = 1,
        per_page: int = 10,
        statuses: Optional[List[str]] = None,
        user_id: Optional[int] = None
    ) -> Tuple[List[Ticket], int]:
        """
        Возвращает одну страницу тикетов с пагинацией.

        Args:
            page (int): номер страницы (начиная с 1).
            per_page (int): количество тикетов на странице.
            statuses (Optional[List[str]]): фильтр по статусам.
            user_id (Optional[int]): фильтр по пользователю.

        Returns:
            Tuple[List[Ticket], int]: список тикетов на текущей странице и общее количество тикетов.
        """

        logger.info(f"get_tickets_page: page={page}, per_page={per_page}, statuses={statuses}, user_id={user_id}")

        async with db.session_maker() as session:
            query = select(Ticket)
            if statuses:
                query = query.where(Ticket.status.in_(statuses))
            if user_id:
                query = query.where(Ticket.user_id == user_id)
            query = query.order_by(Ticket.created_at.desc())

            count_query = select(func.count()).select_from(query.subquery())
            total_count = await session.scalar(count_query) or 0

            query = query.offset((page - 1) * per_page).limit(per_page)
            result = await session.execute(query)
            tickets = result.scalars().all()

            logger.info(f"get_tickets_page: получено {len(tickets)} тикетов, всего {total_count}")

            return tickets, total_count

    @staticmethod
    async def get_tickets_total_pages(
        per_page: int = 10,
        statuses: Optional[List[str]] = None
    ) -> int:
        """
        Вычисляет общее количество страниц для списка тикетов.

        Args:
            per_page (int): количество тикетов на странице.
            statuses (Optional[List[str]]): фильтр по статусам.

        Returns:
            int: общее количество страниц.
        """
        async with db.session_maker() as session:
            query = select(Ticket)
            if statuses:
                query = query.where(Ticket.status.in_(statuses))
            count_query = select(func.count()).select_from(query.subquery())
            total_count = await session.scalar(count_query) or 0
            return (total_count + per_page - 1) // per_page

    @staticmethod
    async def get_user_tickets_count(user_id: int) -> int:
        """
        Возвращает количество тикетов пользователя.

        Args:
            user_id (int): ID пользователя.

        Returns:
            int: количество тикетов.
        """
        async with db.session_maker() as session:
            result = await session.execute(
                select(func.count(Ticket.id)).where(Ticket.user_id == user_id)
            )
            return result.scalar() or 0


# Создаем глобальный экземпляр сервиса (экземпляр класса, все методы статические, это допустимо)
ticket_service = TicketService()
