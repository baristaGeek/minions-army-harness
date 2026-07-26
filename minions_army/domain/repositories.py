"""Domain repository interfaces."""

from abc import ABC, abstractmethod
from typing import Any, Protocol, TypeVar

from minions_army.domain.models import SlackMessage, WebAPIMessage

T = TypeVar("T")


class BaseRepository[T](ABC):
    """Base repository interface."""

    @abstractmethod
    async def get_by_id(self, entity_id: int) -> T | None:
        """Get entity by ID."""
        pass

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        """Get all entities with pagination."""
        pass

    @abstractmethod
    async def create(self, data: dict[str, Any]) -> T:
        """Create new entity."""
        pass

    @abstractmethod
    async def update(self, entity_id: int, data: dict[str, Any]) -> T | None:
        """Update entity."""
        pass

    @abstractmethod
    async def delete(self, entity_id: int) -> bool:
        """Delete entity."""
        pass


class SlackMessageRepository(Protocol):
    """Repository interface for Slack messages."""

    async def create(self, message: SlackMessage) -> SlackMessage:
        """Persist a Slack message."""
        ...


class WebAPIMessageRepository(Protocol):
    """Repository interface for Web API messages."""

    async def create(self, message: WebAPIMessage) -> WebAPIMessage:
        """Persist a Web API message."""
        ...
