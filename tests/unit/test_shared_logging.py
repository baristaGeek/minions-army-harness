"""Tests for shared structured logging helpers."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from minions_army.core.runtime.logging import (
    build_log_message,
    build_step_log_message,
    collapse_log_text,
    format_command,
    log_event,
    log_exception,
    log_subprocess_failure,
    log_welcome_banner,
)


def test_collapse_log_text_normalizes_whitespace_and_truncates() -> None:
    assert collapse_log_text("hello\n  world\t!") == "hello world !"
    assert collapse_log_text("abcdef", max_length=5) == "ab..."


def test_build_log_message_formats_structured_fields() -> None:
    message = build_log_message(
        "sample.event",
        path=Path("/tmp/file.txt"),
        payload={"b": 2, "a": 1},
        items=["x", "y"],
        optional=None,
    )

    assert message.startswith("[MINION][APP][sample.event] event=sample.event")
    assert "path=" in message
    assert "file.txt" in message
    assert 'payload={"a": 1, "b": 2}' in message
    assert 'items=["x", "y"]' in message
    assert "optional=" not in message


def test_build_step_log_message_formats_visible_step_banner() -> None:
    message = build_step_log_message(
        "initialize-workspace",
        "END",
        42,
        execution_id="exec-123",
        step_seq=7,
    )

    assert message.startswith("[MINION][STEP][END] initialize-workspace")
    assert "event=pipeline.step.END" in message
    assert "step_name=initialize-workspace" in message
    assert "execution_id=exec-123" in message
    assert "step_seq=7" in message
    assert "duration_ms=42" in message


def test_format_command_joins_for_logs() -> None:
    assert format_command(["python", "-m", "pytest", "-q"]) == "python -m pytest -q"


def test_log_event_and_log_exception_emit_single_line_messages(caplog) -> None:
    logger = logging.getLogger("tests.shared.logging")

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(logger, logging.INFO, "event.ok", field="value")
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            log_exception(logger, "event.failed", field="value")

    assert "[MINION][APP][event.ok] event=event.ok | field=value" in caplog.text
    assert "[MINION][APP][event.failed] event=event.failed | field=value" in caplog.text


def test_log_welcome_banner_emits_minion_ascii_art(caplog) -> None:
    logger = logging.getLogger("tests.shared.banner")

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_welcome_banner(logger)

    assert "__        __  _____  _      ____  ___  __  __  _____" in caplog.text
    assert '.-"""""""-.' in caplog.text


def test_log_subprocess_failure_records_command_and_output_tails(caplog) -> None:
    logger = logging.getLogger("tests.shared.subprocess")
    completed = subprocess.CompletedProcess(
        args=["git", "status"],
        returncode=2,
        stdout="line1\nline2",
        stderr="err1\nerr2",
    )

    with caplog.at_level(logging.ERROR, logger=logger.name):
        log_subprocess_failure(
            logger,
            "subprocess.failed",
            command=["git", "status"],
            cwd=Path("/repo"),
            completed=completed,
        )

    assert "event=subprocess.failed" in caplog.text
    assert "command=git status" in caplog.text
    assert "cwd=" in caplog.text
    assert "repo" in caplog.text
    assert "exit_code=2" in caplog.text
    assert "stdout_tail=line1 line2" in caplog.text
    assert "stderr_tail=err1 err2" in caplog.text
