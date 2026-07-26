"""Outbound Slack notifications (chat.postMessage).

Best-effort helper shared by the API (immediate acknowledgement) and the minion
pipeline (progress updates). It never raises and no-ops without a bot token or
channel, so Slack outages can never break request handling or the pipeline.
"""

from __future__ import annotations

import json
import logging
import urllib.request

from minions_army.core.runtime.logging import log_event, log_exception

logger = logging.getLogger(__name__)

_SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


def post_slack_message(
    text: str,
    token: str | None,
    channel: str | None,
    thread_ts: str | None = None,
) -> None:
    """Post a message to a Slack channel/thread. Silently no-ops when unconfigured."""
    if not token or not channel:
        return
    payload: dict[str, str] = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    request = urllib.request.Request(
        _SLACK_POST_MESSAGE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310
            body = response.read()
        result = json.loads(body.decode("utf-8") or "{}")
        if not result.get("ok", False):
            log_event(
                logger,
                logging.ERROR,
                "slack.post.rejected",
                channel=channel,
                thread_ts=thread_ts,
                error=result.get("error", "unknown_error"),
            )
            return
        log_event(
            logger,
            logging.INFO,
            "slack.post.succeeded",
            channel=channel,
            thread_ts=thread_ts,
        )
    except Exception:
        log_exception(logger, "slack.post.failed", channel=channel, thread_ts=thread_ts)
