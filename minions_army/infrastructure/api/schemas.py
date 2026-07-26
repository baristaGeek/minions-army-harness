"""API request and response models."""

import re

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from minions_army.application.services.webhook_service import (
    SlackMessageInput,
    WebAPIMessageInput,
)

# Leading Slack mention(s), e.g. "<@U08ABCDEF> make the app blue".
_LEADING_MENTION = re.compile(r"^\s*(?:<@[A-Z0-9]+>\s*)+")


def _strip_leading_mention(text: str) -> str:
    """Remove a leading @mention so '@minions make it blue' -> 'make it blue'."""
    return _LEADING_MENTION.sub("", text).strip()


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    error_code: str | None = None
    status_code: int


class SlackEventPayload(BaseModel):
    """Slack event payload nested under the Events API envelope."""

    model_config = ConfigDict(populate_by_name=True)

    type: str | None = None
    channel_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("channel_id", "channel"),
    )
    text: str | None = None
    user_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("user_id", "user"),
    )
    slack_event_ts: str | None = Field(
        default=None,
        validation_alias=AliasChoices("slack_event_ts", "event_ts", "ts"),
    )


class SlackWebhookRequest(BaseModel):
    """Accepted Slack webhook payload.

    Supports Slack Events API messages and a simple payload for local testing.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str | None = None
    event: SlackEventPayload | None = None
    channel_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("channel_id", "channel"),
    )
    text: str | None = None
    user_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("user_id", "user"),
    )
    slack_event_ts: str | None = Field(
        default=None,
        validation_alias=AliasChoices("slack_event_ts", "event_ts", "ts"),
    )
    challenge: str | None = None

    @model_validator(mode="after")
    def ensure_message_fields(self) -> "SlackWebhookRequest":
        """Ensure the payload contains enough data to process a text message."""
        if self.challenge:
            return self

        channel_id = self.event.channel_id if self.event else self.channel_id
        text = self.event.text if self.event else self.text
        if not channel_id:
            raise ValueError("Slack payload must include a channel")
        if text is None:
            raise ValueError("Slack payload must include text")
        return self

    def to_input(self) -> SlackMessageInput:
        """Convert API payload into application input."""
        event = self.event
        text = (event.text if event else self.text) or ""
        return SlackMessageInput(
            channel_id=(event.channel_id if event else self.channel_id) or "",
            text=_strip_leading_mention(text),
            user_id=(event.user_id if event else self.user_id),
            slack_event_ts=(event.slack_event_ts if event else self.slack_event_ts),
            raw_payload=self.model_dump(mode="json"),
        )


class SlackWebhookAcceptedResponse(BaseModel):
    """Response returned after accepting the webhook."""

    status: str
    message_id: int | None = None
    challenge: str | None = None


class WebAPIWebhookAcceptedResponse(BaseModel):
    """Response returned after accepting the Web API webhook."""

    status: str
    message_id: int | None = None
    session_id: str


class WebAPIWebhookRequest(BaseModel):
    """Accepted Web API payload."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    session_id: str = Field(validation_alias=AliasChoices("session_id", "sessionId"))
    text: str
    user_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("user_id", "userId", "user"),
    )

    @model_validator(mode="after")
    def ensure_message_fields(self) -> "WebAPIWebhookRequest":
        """Ensure the payload contains enough data to process a message."""
        if not self.session_id.strip():
            raise ValueError("Web API payload must include a session id")
        if not self.text.strip():
            raise ValueError("Web API payload must include text")
        return self

    def to_input(self) -> WebAPIMessageInput:
        """Convert API payload into application input."""
        return WebAPIMessageInput(
            session_id=self.session_id,
            text=self.text,
            user_id=self.user_id,
            raw_payload=self.model_dump(mode="json"),
        )


