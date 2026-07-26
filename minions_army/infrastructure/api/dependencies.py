"""FastAPI dependency providers."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from minions_army.application.services.webhook_service import (
    SlackWebhookService,
    WebAPIWebhookService,
)
from minions_army.core.config.loader import config as settings
from minions_army.infrastructure.launchers.factory import build_minion_task_runner
from minions_army.infrastructure.persistence.database import get_session
from minions_army.infrastructure.persistence.repositories import (
    SQLAlchemySlackMessageRepository,
    SQLAlchemyWebAPIMessageRepository,
)


async def get_slack_webhook_service(
    session: AsyncSession = Depends(get_session),
) -> SlackWebhookService:
    """Build the Slack webhook use case."""
    repository = SQLAlchemySlackMessageRepository(session)
    runner = build_minion_task_runner()
    return SlackWebhookService(
        repository=repository,
        minion_runner=runner,
        allowed_channel_id=settings.slack.allowed_channel_id,
    )


def get_slack_webhook_service_factory():
    """Build a lazy Slack webhook service factory.

    This keeps request-time dependency resolution free of database access until
    the endpoint knows it is handling a non-challenge Slack message.
    """

    def factory(session: AsyncSession) -> SlackWebhookService:
        repository = SQLAlchemySlackMessageRepository(session)
        runner = build_minion_task_runner()
        return SlackWebhookService(
            repository=repository,
            minion_runner=runner,
            allowed_channel_id=settings.slack.allowed_channel_id,
        )

    return factory


def get_webapi_webhook_service_factory():
    """Build a lazy Web API webhook service factory."""

    def factory(session: AsyncSession) -> WebAPIWebhookService:
        repository = SQLAlchemyWebAPIMessageRepository(session)
        runner = build_minion_task_runner()
        return WebAPIWebhookService(repository=repository, minion_runner=runner)

    return factory
