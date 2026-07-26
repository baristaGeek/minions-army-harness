"""Tests for domain exceptions."""

from minions_army.domain.exceptions import (
    ConflictError,
    DomainException,
    EntityNotFoundError,
    ValidationError,
)


def test_entity_not_found_error_exposes_context() -> None:
    error = EntityNotFoundError("SlackMessage", 7)

    assert isinstance(error, DomainException)
    assert error.entity_name == "SlackMessage"
    assert error.identifier == 7
    assert str(error) == "SlackMessage with identifier 7 not found"


def test_validation_and_conflict_errors_preserve_message() -> None:
    validation_error = ValidationError("bad input")
    conflict_error = ConflictError("duplicate")

    assert isinstance(validation_error, DomainException)
    assert isinstance(conflict_error, DomainException)
    assert str(validation_error) == "bad input"
    assert str(conflict_error) == "duplicate"
