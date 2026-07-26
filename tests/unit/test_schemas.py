"""Tests for API schemas."""

from minions_army.infrastructure.api.schemas import (
    SlackWebhookRequest,
    WebAPIWebhookRequest,
)


def test_slack_webhook_request_to_input_uses_nested_event() -> None:
    request = SlackWebhookRequest(
        event={"channel": "C123", "text": "hello", "user": "U1", "ts": "123.4"}
    )

    payload = request.to_input()

    assert payload.channel_id == "C123"
    assert payload.text == "hello"
    assert payload.user_id == "U1"
    assert payload.slack_event_ts == "123.4"


def test_slack_webhook_request_strips_leading_mention() -> None:
    request = SlackWebhookRequest(
        event={"channel": "C123", "text": "<@U0BOT> make the app blue", "ts": "1.2"}
    )

    payload = request.to_input()

    assert payload.text == "make the app blue"


def test_slack_webhook_request_strips_multiple_leading_mentions() -> None:
    request = SlackWebhookRequest(
        event={"channel": "C123", "text": "<@U0BOT> <@U0OTHER>   ship it", "ts": "1.2"}
    )

    assert request.to_input().text == "ship it"


def test_slack_webhook_request_allows_challenge_only() -> None:
    request = SlackWebhookRequest(challenge="abc123")

    assert request.challenge == "abc123"


def test_webapi_webhook_request_to_input_accepts_session_id_alias() -> None:
    request = WebAPIWebhookRequest(sessionId="session-123", text="ship it", user="user-123")

    payload = request.to_input()

    assert payload.session_id == "session-123"
    assert payload.text == "ship it"
    assert payload.user_id == "user-123"
    assert payload.raw_payload["session_id"] == "session-123"
