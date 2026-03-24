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
    """Raised when an action conflicts with the current state (e.g. duplicate)."""


class ValidationException(FineloBaseException):
    """Raised when business validation fails (distinct from Pydantic schema validation)."""


class AttemptAlreadyCompletedException(ConflictException):
    """Raised when trying to submit an already-completed attempt."""


class InsufficientBalanceException(FineloBaseException):
    """Raised when a debit would exceed the current balance."""


class IdempotencyMismatchError(FineloBaseException):
    """Raised when an idempotency key is reused with a different payload."""