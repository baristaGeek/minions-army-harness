"""Domain exceptions and error handling."""


class DomainException(Exception):
    """Base exception for domain errors."""

    pass


class EntityNotFoundError(DomainException):
    """Exception raised when an entity is not found."""

    def __init__(self, entity_name: str, identifier: str | int):
        self.entity_name = entity_name
        self.identifier = identifier
        super().__init__(f"{entity_name} with identifier {identifier} not found")


class ValidationError(DomainException):
    """Exception raised when validation fails."""

    def __init__(self, message: str):
        super().__init__(message)


class ConflictError(DomainException):
    """Exception raised when a conflict occurs (e.g., duplicate)."""

    def __init__(self, message: str):
        super().__init__(message)
