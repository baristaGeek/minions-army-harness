"""API routes."""

import logging
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from minions_army.application.services.webhook_service import (
    SlackWebhookService,
    WebAPIWebhookService,
)
from minions_army.core.runtime.logging import log_event
from minions_army.domain.exceptions import ValidationError
from minions_army.domain.models import SlackMessage, WebAPIMessage
from minions_army.infrastructure.api.dependencies import (
    get_slack_webhook_service_factory,
    get_webapi_webhook_service_factory,
)
from minions_army.infrastructure.api.schemas import (
    SlackWebhookAcceptedResponse,
    SlackWebhookRequest,
    WebAPIWebhookAcceptedResponse,
    WebAPIWebhookRequest,
)
from minions_army.infrastructure.persistence.database import _get_sessionmaker

router = APIRouter(prefix="/api/v1", tags=["default"])
logger = logging.getLogger(__name__)


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Welcome to Minions Army API"}


@router.post(
    "/webhooks/slack/messages",
    response_model=SlackWebhookAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["webhooks"],
)
async def receive_slack_message(
    payload: SlackWebhookRequest,
    background_tasks: BackgroundTasks,
    service_factory: Callable[[AsyncSession], SlackWebhookService] = Depends(
        get_slack_webhook_service_factory
    ),
) -> SlackWebhookAcceptedResponse:
    """Receive a Slack text message, persist it, and start a minion workload."""
    log_event(
        logger,
        logging.INFO,
        "slack.webhook.received",
        has_challenge=bool(payload.challenge),
        channel_id=payload.channel_id,
        user_id=payload.user_id,
    )
    if payload.challenge:
        log_event(logger, logging.INFO, "slack.webhook.challenge.responded")
        return SlackWebhookAcceptedResponse(status="ok", challenge=payload.challenge)

    async with _get_sessionmaker()() as session:
        service = service_factory(session)
        message_input = payload.to_input()
        try:
            message = await service.accept_message(message_input)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except Exception:
            log_event(
                logger,
                logging.WARNING,
                "slack.webhook.persistence.skipped",
                channel_id=message_input.channel_id,
                user_id=message_input.user_id,
            )
            message = SlackMessage(
                id=None,
                channel_id=message_input.channel_id,
                text=message_input.text,
                user_id=message_input.user_id,
                slack_event_ts=message_input.slack_event_ts,
                raw_payload=message_input.raw_payload,
                created_at=None,
                updated_at=None,
            )

        log_event(
            logger,
            logging.INFO,
            "slack.webhook.accepted",
            message_id=message.id,
            channel_id=message.channel_id,
            user_id=message.user_id,
        )
        background_tasks.add_task(service.run_container_for_message, message)
        return SlackWebhookAcceptedResponse(status="accepted", message_id=message.id)


@router.post(
    "/webhooks/webapi/messages",
    response_model=WebAPIWebhookAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["webhooks"],
)
async def receive_webapi_message(
    payload: WebAPIWebhookRequest,
    background_tasks: BackgroundTasks,
    service_factory: Callable[[AsyncSession], WebAPIWebhookService] = Depends(
        get_webapi_webhook_service_factory
    ),
) -> WebAPIWebhookAcceptedResponse:
    """Receive a Web API message, persist it, and start a minion workload."""
    log_event(
        logger,
        logging.INFO,
        "webapi.webhook.received",
        session_id=payload.session_id,
        user_id=payload.user_id,
    )

    async with _get_sessionmaker()() as session:
        service = service_factory(session)
        message_input = payload.to_input()
        # TODO: Re-enable Web API persistence when database writes are needed.
        # try:
        #     message = await service.accept_message(message_input)
        # except ValidationError as exc:
        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST,
        #         detail=str(exc),
        #     ) from exc
        # except Exception:
        #     log_event(
        #         logger,
        #         logging.WARNING,
        #         "webapi.webhook.persistence.skipped",
        #         session_id=message_input.session_id,
        #         user_id=message_input.user_id,
        #     )
        #     message = WebAPIMessage(
        #         id=None,
        #         session_id=message_input.session_id,
        #         text=message_input.text,
        #         user_id=message_input.user_id,
        #         raw_payload=message_input.raw_payload,
        #         created_at=None,
        #         updated_at=None,
        #     )
        message = WebAPIMessage(
            id=None,
            session_id=message_input.session_id,
            text=message_input.text,
            user_id=message_input.user_id,
            raw_payload=message_input.raw_payload,
            created_at=None,
            updated_at=None,
        )

        log_event(
            logger,
            logging.INFO,
            "webapi.webhook.accepted",
            message_id=message.id,
            session_id=message.session_id,
            user_id=message.user_id,
        )
        background_tasks.add_task(service.run_container_for_message, message)
        return WebAPIWebhookAcceptedResponse(
            status="accepted",
            message_id=message.id,
            session_id=message.session_id,
        )
