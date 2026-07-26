"""Example SQLAlchemy repository implementation."""

from typing import Any, Protocol, TypeVar, cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from minions_army.domain.models import SlackMessage, WebAPIMessage
from minions_army.domain.repositories import BaseRepository
from minions_army.infrastructure.persistence.models import (
    SlackMessageORM,
    WebAPIMessageORM,
)

T = TypeVar("T")


class HasId(Protocol):
    """ORM model protocol for repositories that query by ID."""

    id: Any


class SQLAlchemyRepository[T, ModelType: HasId](BaseRepository[T]):
    """Base SQLAlchemy repository implementation."""

    def __init__(self, session: AsyncSession, model: type[ModelType]):
        """Initialize repository.

        Args:
            session: Async SQLAlchemy session
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model

    async def get_by_id(self, entity_id: int) -> T | None:
        """Get entity by ID."""
        stmt = select(self.model).where(self.model.id == entity_id)
        result = await self.session.execute(stmt)
        return cast(T | None, result.scalar_one_or_none())

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        """Get all entities with pagination."""
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return cast(list[T], list(result.scalars().all()))

    async def create(self, data: dict[str, Any]) -> T:
        """Create new entity."""
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        return cast(T, instance)

    async def update(self, entity_id: int, data: dict[str, Any]) -> T | None:
        """Update entity."""
        entity = await self.get_by_id(entity_id)
        if not entity:
            return None
        for key, value in data.items():
            setattr(entity, key, value)
        await self.session.flush()
        return entity

    async def delete(self, entity_id: int) -> bool:
        """Delete entity."""
        entity = await self.get_by_id(entity_id)
        if not entity:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True


class SQLAlchemySlackMessageRepository:
    """SQLAlchemy repository for Slack messages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, message: SlackMessage) -> SlackMessage:
        """Persist a Slack message and commit the transaction."""
        instance = SlackMessageORM(
            channel_id=message.channel_id,
            text=message.text,
            user_id=message.user_id,
            slack_event_ts=message.slack_event_ts,
            raw_payload=message.raw_payload,
        )
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return self._to_domain(instance)

    @staticmethod
    def _to_domain(instance: SlackMessageORM) -> SlackMessage:
        return SlackMessage(
            id=instance.id,
            channel_id=instance.channel_id,
            text=instance.text,
            user_id=instance.user_id,
            slack_event_ts=instance.slack_event_ts,
            raw_payload=instance.raw_payload,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        )


class SQLAlchemyWebAPIMessageRepository:
    """SQLAlchemy repository for Web API messages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, message: WebAPIMessage) -> WebAPIMessage:
        """Persist a Web API message and commit the transaction."""
        instance = WebAPIMessageORM(
            session_id=message.session_id,
            text=message.text,
            user_id=message.user_id,
            raw_payload=message.raw_payload,
        )
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return self._to_domain(instance)

    @staticmethod
    def _to_domain(instance: WebAPIMessageORM) -> WebAPIMessage:
        return WebAPIMessage(
            id=instance.id,
            session_id=instance.session_id,
            text=instance.text,
            user_id=instance.user_id,
            raw_payload=instance.raw_payload,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        )
