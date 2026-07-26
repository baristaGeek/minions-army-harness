"""Domain entities."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseEntity(BaseModel):
    """Base entity model with common fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(None, description="Entity ID")
    created_at: datetime | None = Field(None, description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")


class SlackMessage(BaseEntity):
    """Slack text message accepted by the webhook."""

    channel_id: str = Field(..., description="Slack channel ID")
    text: str = Field(..., description="Slack message text")
    user_id: str | None = Field(None, description="Slack user ID")
    slack_event_ts: str | None = Field(None, description="Slack event timestamp")
    raw_payload: dict[str, Any] = Field(
        default_factory=dict, description="Original webhook payload"
    )


class WebAPIMessage(BaseEntity):
    """Web API message accepted by the webhook."""

    session_id: str = Field(..., description="Web API session ID")
    text: str = Field(..., description="Web API message text")
    user_id: str | None = Field(None, description="Web API user ID")
    raw_payload: dict[str, Any] = Field(
        default_factory=dict, description="Original webhook payload"
    )
