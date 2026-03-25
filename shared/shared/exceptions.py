from __future__ import annotations


class FineloBaseException(Exception):
    """Base exception for all Finelo domain errors."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__


class NotFoundException(FineloBaseException):
    """Raised when a requested resource is not found."""


class ConflictException(FineloBaseException):
    """Raised when an action conflicts with the current state."""


class ValidationException(FineloBaseException):
    """Raised when business validation fails (distinct from Pydantic errors)."""


class ForbiddenException(FineloBaseException):
    """Raised when a user attempts to access a resource they do not own."""


class InternalServerException(FineloBaseException):
    """Raised when a critical internal failure occurs that is still a 'known' error."""


class AttemptAlreadyCompletedException(ConflictException):
    """Raised when trying to modify or submit an already-completed attempt."""


class AttemptExpiredException(ConflictException):
    """
    Raised when an attempt is too old to be modified or submitted.
    Used by both the Reaper worker and 'Lazy Evaluation' logic.
    """


class InsufficientBalanceException(FineloBaseException):
    """Raised when a debit would exceed the current balance."""


class IdempotencyMismatchError(ConflictException):
    """Raised when an idempotency key is reused with a different payload."""