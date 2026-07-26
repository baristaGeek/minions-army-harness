"""Tests for Web API webhook use case."""

import pytest

from minions_army.application.services.webhook_service import (
    WebAPIMessageInput,
    WebAPIWebhookService,
)
from minions_army.domain.exceptions import ValidationError
from minions_army.domain.models import WebAPIMessage


class FakeWebAPIMessageRepository:
    def __init__(self) -> None:
        self.messages: list[WebAPIMessage] = []

    async def create(self, message: WebAPIMessage) -> WebAPIMessage:
        self.messages.append(message)
        return message.model_copy(update={"id": 9})


class FakeDockerTaskRunner:
    def __init__(self) -> None:
        self.messages: list[WebAPIMessage] = []

    def run_for_message(self, message: WebAPIMessage) -> None:
        self.messages.append(message)


@pytest.mark.asyncio
async def test_accept_message_persists_webapi_message() -> None:
    repository = FakeWebAPIMessageRepository()
    runner = FakeDockerTaskRunner()
    service = WebAPIWebhookService(repository, runner)

    message = await service.accept_message(
        WebAPIMessageInput(
            session_id="session-123",
            text="ship it",
            user_id="user-123",
            raw_payload={"source": "test"},
        )
    )

    assert message.id == 9
    assert message.session_id == "session-123"
    assert message.text == "ship it"
    assert message.user_id == "user-123"
    assert repository.messages[0].raw_payload == {"source": "test"}


@pytest.mark.asyncio
async def test_accept_message_rejects_empty_session_id() -> None:
    service = WebAPIWebhookService(FakeWebAPIMessageRepository(), FakeDockerTaskRunner())

    with pytest.raises(ValidationError, match="session id"):
        await service.accept_message(WebAPIMessageInput(session_id=" ", text="hello"))


@pytest.mark.asyncio
async def test_accept_message_rejects_empty_text() -> None:
    service = WebAPIWebhookService(FakeWebAPIMessageRepository(), FakeDockerTaskRunner())

    with pytest.raises(ValidationError, match="message text"):
        await service.accept_message(WebAPIMessageInput(session_id="session-123", text="   "))


def test_run_container_for_message_delegates_to_runner() -> None:
    runner = FakeDockerTaskRunner()
    service = WebAPIWebhookService(FakeWebAPIMessageRepository(), runner)
    message = WebAPIMessage(id=9, session_id="session-123", text="hello")

    service.run_container_for_message(message)

    assert runner.messages == [message]
