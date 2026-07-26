"""Tests for the outbound Slack notifier."""

import logging

from minions_army.infrastructure.integrations.slack import notifier as slack_notifier
from minions_army.infrastructure.integrations.slack.notifier import post_slack_message


def test_post_slack_message_noops_without_token(monkeypatch, caplog) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        slack_notifier.urllib.request, "urlopen", lambda *a, **k: called.append("sent")
    )

    with caplog.at_level(logging.INFO):
        post_slack_message("hi", token=None, channel="C1")
        post_slack_message("hi", token="t", channel=None)

    assert called == []
    assert "event=slack.post.skipped" not in caplog.text


def test_post_slack_message_posts_with_thread(monkeypatch, caplog) -> None:
    recorded: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request):
        recorded["url"] = request.full_url
        recorded["headers"] = request.headers
        recorded["body"] = request.data
        return FakeResponse()

    monkeypatch.setattr(slack_notifier.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.INFO):
        post_slack_message("shipped", token="xoxb-1", channel="C123", thread_ts="1.2")

    assert recorded["url"] == "https://slack.com/api/chat.postMessage"
    assert b'"thread_ts": "1.2"' in recorded["body"]
    assert b'"channel": "C123"' in recorded["body"]
    assert "event=slack.post.succeeded" in caplog.text
    assert "channel=C123" in caplog.text


def test_post_slack_message_logs_slack_api_rejection(monkeypatch, caplog) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok": false, "error": "not_in_channel"}'

    monkeypatch.setattr(
        slack_notifier.urllib.request,
        "urlopen",
        lambda *a, **k: FakeResponse(),
    )

    with caplog.at_level(logging.ERROR):
        post_slack_message("hi", token="xoxb-1", channel="C123", thread_ts="1.2")

    assert "event=slack.post.rejected" in caplog.text
    assert "error=not_in_channel" in caplog.text


def test_post_slack_message_swallows_errors(monkeypatch, caplog) -> None:
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(slack_notifier.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.ERROR):
        # Must not raise.
        post_slack_message("x", token="t", channel="C1")

    assert "event=slack.post.failed" in caplog.text
