from collections.abc import Callable
from typing import Any

from validated.validators.base import Validator
from validated.validators.exceptions import ValidatorCheckError


class Check(Validator):
    def __init__(self, predicate: Callable[[Any], bool], description: str | None = None):
        self.predicate = predicate
        self.description = description or getattr(predicate, "__name__", None) or "custom predicate"

    def validate(self, value: Any) -> bool:
        try:
            return bool(self.predicate(value))
        except Exception as exc:
            raise ValidatorCheckError(
                f"Predicate '{self.description}' raised {type(exc).__name__}: {exc}",
                original_exception=exc,
            ) from exc

    def error_message(self, value: Any) -> str:
        return f"must satisfy custom check: {self.description}"

    def __repr__(self) -> str:
        return f"Check(description={self.description!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Check) and self.predicate is other.predicate and self.description == other.description
