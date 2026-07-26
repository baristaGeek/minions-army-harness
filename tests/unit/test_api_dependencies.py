"""Tests for API dependency providers."""

import pytest

from minions_army.application.services.webhook_service import (
    SlackWebhookService,
    WebAPIWebhookService,
)
from minions_army.infrastructure.api.dependencies import (
    get_slack_webhook_service,
    get_webapi_webhook_service_factory,
)


@pytest.mark.asyncio
async def test_get_slack_webhook_service_builds_expected_service(monkeypatch) -> None:
    monkeypatch.setattr(
        "minions_army.infrastructure.api.dependencies.settings.slack.allowed_channel_id", "C123"
    )
    service = await get_slack_webhook_service(session=object())

    assert isinstance(service, SlackWebhookService)
    assert service.allowed_channel_id == "C123"


def test_get_webapi_webhook_service_factory_builds_service() -> None:
    factory = get_webapi_webhook_service_factory()
    service = factory(session=object())

    assert isinstance(service, WebAPIWebhookService)
