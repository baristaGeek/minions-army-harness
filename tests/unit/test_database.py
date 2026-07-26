"""Tests for database helpers."""

from unittest.mock import patch

import pytest

import minions_army.infrastructure.persistence.database as database


def test_get_engine_is_lazy(monkeypatch) -> None:
    monkeypatch.setattr(database, "engine", None)
    monkeypatch.setattr(database.settings.database, "url", "sqlite+aiosqlite:///test.db")
    monkeypatch.setattr(database.settings.app, "debug", True)

    with patch(
        "minions_army.infrastructure.persistence.database.create_async_engine"
    ) as mock_create:
        engine = database._get_engine()

    assert engine == mock_create.return_value
    mock_create.assert_called_once()


def test_get_sessionmaker_is_lazy(monkeypatch) -> None:
    monkeypatch.setattr(database, "engine", object())
    monkeypatch.setattr(database, "AsyncSessionLocal", None)

    with patch(
        "minions_army.infrastructure.persistence.database.async_sessionmaker"
    ) as mock_factory:
        sessionmaker = database._get_sessionmaker()

    assert sessionmaker == mock_factory.return_value
    mock_factory.assert_called_once()


@pytest.mark.asyncio
async def test_get_session_yields_session(monkeypatch) -> None:
    class FakeContextManager:
        async def __aenter__(self):
            return "session"

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(database, "_get_sessionmaker", lambda: lambda: FakeContextManager())

    sessions = []
    async for session in database.get_session():
        sessions.append(session)

    assert sessions == ["session"]
