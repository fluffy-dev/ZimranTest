from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    def __repr__(self) -> str:
        """Dynamic representation of the model instance including its primary key and columns."""
        cols = ", ".join(
            f"{c.key}={getattr(self, c.key)!r}"
            for c in self.__table__.columns
            if hasattr(self, c.key)
        )
        return f"{self.__class__.__name__}({cols})"
