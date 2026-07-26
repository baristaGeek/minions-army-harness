"""Tests for repository implementations."""

from unittest.mock import AsyncMock

import pytest

from minions_army.domain.models import SlackMessage, WebAPIMessage
from minions_army.infrastructure.persistence.models import (
    SlackMessageORM,
    WebAPIMessageORM,
)
from minions_army.infrastructure.persistence.repositories import (
    SQLAlchemyRepository,
    SQLAlchemySlackMessageRepository,
    SQLAlchemyWebAPIMessageRepository,
)


class FakeResult:
    def __init__(self, item=None, items=None) -> None:
        self._item = item
        self._items = items or []

    def scalar_one_or_none(self):
        return self._item

    def scalars(self):
        return self

    def all(self):
        return self._items


@pytest.mark.asyncio
async def test_sqlalchemy_repository_crud_happy_path() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.added: list[SlackMessageORM] = []
            self.deleted: list[SlackMessageORM] = []
            self.execute = AsyncMock(
                side_effect=[
                    FakeResult(SlackMessageORM(channel_id="C1", text="one")),
                    FakeResult(
                        items=[
                            SlackMessageORM(channel_id="C1", text="one"),
                            SlackMessageORM(channel_id="C2", text="two"),
                        ]
                    ),
                    FakeResult(SlackMessageORM(channel_id="C1", text="one")),
                    FakeResult(SlackMessageORM(channel_id="C1", text="one")),
                    FakeResult(None),
                ]
            )
            self.flush = AsyncMock()
            self.delete = AsyncMock(side_effect=self.deleted.append)

        def add(self, instance: SlackMessageORM) -> None:
            self.added.append(instance)

    session = FakeSession()
    repo = SQLAlchemyRepository[SlackMessageORM, SlackMessageORM](session, SlackMessageORM)

    created = await repo.create({"channel_id": "C3", "text": "new"})
    assert created.text == "new"
    assert session.added[0].text == "new"

    fetched = await repo.get_by_id(1)
    assert fetched is not None and fetched.text == "one"

    all_items = await repo.get_all()
    assert len(all_items) == 2

    updated = await repo.update(1, {"text": "updated"})
    assert updated is not None and updated.text == "updated"

    deleted = await repo.delete(1)
    assert deleted is True
    assert len(session.deleted) == 1


@pytest.mark.asyncio
async def test_sqlalchemy_slack_message_repository_to_domain_roundtrip() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.added: list[object] = []
            self.commit = AsyncMock()
            self.refresh = AsyncMock()

        def add(self, instance: object) -> None:
            self.added.append(instance)

    session = FakeSession()
    repo = SQLAlchemySlackMessageRepository(session)
    message = SlackMessage(channel_id="C123", text="hello", user_id="U1", slack_event_ts="1")

    created = await repo.create(message)

    assert created.channel_id == "C123"
    assert created.text == "hello"
    assert session.added and isinstance(session.added[0], SlackMessageORM)

    orm = SlackMessageORM(
        channel_id="C123",
        text="hello",
        user_id="U1",
        slack_event_ts="1",
        raw_payload={"x": 1},
    )
    orm.id = 7
    domain = repo._to_domain(orm)

    assert domain.id == 7
    assert domain.raw_payload == {"x": 1}


@pytest.mark.asyncio
async def test_sqlalchemy_webapi_message_repository_to_domain_roundtrip() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.added: list[object] = []
            self.commit = AsyncMock()
            self.refresh = AsyncMock()

        def add(self, instance: object) -> None:
            self.added.append(instance)

    session = FakeSession()
    repo = SQLAlchemyWebAPIMessageRepository(session)
    message = WebAPIMessage(
        session_id="session-123",
        text="hello",
        user_id="user@example.com",
        raw_payload={"x": 1},
    )

    created = await repo.create(message)

    assert created.session_id == "session-123"
    assert created.text == "hello"
    assert session.added and isinstance(session.added[0], WebAPIMessageORM)

    orm = WebAPIMessageORM(
        session_id="session-123",
        text="hello",
        user_id="user@example.com",
        raw_payload={"x": 1},
    )
    orm.id = 9
    domain = repo._to_domain(orm)

    assert domain.id == 9
    assert domain.session_id == "session-123"
    assert domain.raw_payload == {"x": 1}
