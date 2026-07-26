"""Tests for Slack webhook use case."""

import pytest

from minions_army.application.services.webhook_service import (
    SlackMessageInput,
    SlackWebhookService,
)
from minions_army.domain.exceptions import ValidationError
from minions_army.domain.models import SlackMessage


class FakeSlackMessageRepository:
    def __init__(self) -> None:
        self.messages: list[SlackMessage] = []

    async def create(self, message: SlackMessage) -> SlackMessage:
        saved = message.model_copy(update={"id": len(self.messages) + 1})
        self.messages.append(saved)
        return saved


class FakeDockerTaskRunner:
    def __init__(self) -> None:
        self.messages: list[SlackMessage] = []

    def run_for_message(self, message: SlackMessage) -> None:
        self.messages.append(message)


@pytest.mark.asyncio
async def test_accept_message_persists_valid_payload() -> None:
    repository = FakeSlackMessageRepository()
    runner = FakeDockerTaskRunner()
    service = SlackWebhookService(repository, runner, allowed_channel_id="C123")

    message = await service.accept_message(
        SlackMessageInput(
            channel_id="C123",
            text="run this minion",
            user_id="U123",
            raw_payload={"channel": "C123", "text": "run this minion"},
        )
    )

    assert message.id == 1
    assert message.text == "run this minion"
    assert repository.messages == [message]


@pytest.mark.asyncio
async def test_accept_message_rejects_unexpected_channel() -> None:
    service = SlackWebhookService(
        FakeSlackMessageRepository(),
        FakeDockerTaskRunner(),
        allowed_channel_id="C123",
    )

    with pytest.raises(ValidationError, match="channel is not allowed"):
        await service.accept_message(SlackMessageInput(channel_id="C999", text="hello"))


@pytest.mark.asyncio
async def test_accept_message_rejects_empty_text() -> None:
    service = SlackWebhookService(FakeSlackMessageRepository(), FakeDockerTaskRunner())

    with pytest.raises(ValidationError, match="cannot be empty"):
        await service.accept_message(SlackMessageInput(channel_id="C123", text="   "))


def test_run_container_for_message_delegates_to_runner() -> None:
    runner = FakeDockerTaskRunner()
    service = SlackWebhookService(FakeSlackMessageRepository(), runner)
    message = SlackMessage(id=7, channel_id="C123", text="hello")

    service.run_container_for_message(message)

    assert runner.messages == [message]
