"""Application services."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol

from minions_army.domain.exceptions import ValidationError
from minions_army.domain.models import SlackMessage, WebAPIMessage
from minions_army.domain.repositories import (
    SlackMessageRepository,
    WebAPIMessageRepository,
)


class BaseService[T](ABC):
    """Base service class for business logic."""

    @abstractmethod
    async def get_by_id(self, entity_id: int) -> T | None:
        """Get entity by ID."""
        pass

    @abstractmethod
    async def create(self, data: dict) -> T:
        """Create new entity."""
        pass

    @abstractmethod
    async def update(self, entity_id: int, data: dict) -> T | None:
        """Update entity."""
        pass

    @abstractmethod
    async def delete(self, entity_id: int) -> bool:
        """Delete entity."""
        pass


@dataclass(frozen=True)
class SlackMessageInput:
    """Normalized Slack message input."""

    channel_id: str
    text: str
    user_id: str | None = None
    slack_event_ts: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebAPIMessageInput:
    """Normalized Web API message input."""

    session_id: str
    text: str
    user_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


class MinionTaskRunner(Protocol):
    """Runs containers for persisted webhook messages."""

    def run_for_message(
        self, message: SlackMessage | WebAPIMessage
    ) -> None:
        """Start a container using the webhook message as input."""
        ...


class SlackWebhookService:
    """Use case for receiving Slack text messages."""

    def __init__(
        self,
        repository: SlackMessageRepository,
        minion_runner: MinionTaskRunner,
        allowed_channel_id: str | None = None,
    ) -> None:
        self.repository = repository
        self.minion_runner = minion_runner
        self.allowed_channel_id = allowed_channel_id

    async def accept_message(self, payload: SlackMessageInput) -> SlackMessage:
        """Validate and persist a Slack message."""
        if not payload.text.strip():
            raise ValidationError("Slack message text cannot be empty")

        if self.allowed_channel_id and payload.channel_id != self.allowed_channel_id:
            raise ValidationError("Slack message channel is not allowed")

        message = SlackMessage(
            id=None,
            channel_id=payload.channel_id,
            text=payload.text,
            user_id=payload.user_id,
            slack_event_ts=payload.slack_event_ts,
            raw_payload=payload.raw_payload,
            created_at=None,
            updated_at=None,
        )
        return await self.repository.create(message)

    def run_container_for_message(self, message: SlackMessage) -> None:
        """Run the configured minion task for a previously saved message."""
        self.minion_runner.run_for_message(message)


class WebAPIWebhookService:
    """Use case for receiving Web API messages."""

    def __init__(
        self,
        repository: WebAPIMessageRepository,
        minion_runner: MinionTaskRunner,
    ) -> None:
        self.repository = repository
        self.minion_runner = minion_runner

    async def accept_message(self, payload: WebAPIMessageInput) -> WebAPIMessage:
        """Validate and persist a Web API message."""
        if not payload.session_id.strip():
            raise ValidationError("Web API session id cannot be empty")

        if not payload.text.strip():
            raise ValidationError("Web API message text cannot be empty")

        message = WebAPIMessage(
            id=None,
            session_id=payload.session_id,
            text=payload.text,
            user_id=payload.user_id,
            raw_payload=payload.raw_payload,
            created_at=None,
            updated_at=None,
        )
        return await self.repository.create(message)

    def run_container_for_message(self, message: WebAPIMessage) -> None:
        """Run the configured minion task for a previously saved message."""
        self.minion_runner.run_for_message(message)
