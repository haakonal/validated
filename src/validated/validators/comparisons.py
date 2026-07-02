from typing import Any

from validated.validators.base import Validator


class GreaterThan(Validator):
    def __init__(self, threshold: Any):
        self.threshold = threshold

    def validate(self, value: Any) -> bool:
        return bool(value > self.threshold)

    def error_message(self, value: Any) -> str:
        return f"must be greater than {self.threshold}"

    def __repr__(self) -> str:
        return f"GreaterThan(threshold={self.threshold!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GreaterThan) and self.threshold == other.threshold


class LessThan(Validator):
    def __init__(self, threshold: Any):
        self.threshold = threshold

    def validate(self, value: Any) -> bool:
        return bool(value < self.threshold)

    def error_message(self, value: Any) -> str:
        return f"must be less than {self.threshold}"

    def __repr__(self) -> str:
        return f"LessThan(threshold={self.threshold!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, LessThan) and self.threshold == other.threshold


class InRange(Validator):
    def __init__(self, min_val: Any, max_val: Any):
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, value: Any) -> bool:
        return bool(self.min_val <= value <= self.max_val)

    def error_message(self, value: Any) -> str:
        return f"must be in range [{self.min_val}, {self.max_val}]"

    def __repr__(self) -> str:
        return f"InRange(min_val={self.min_val!r}, max_val={self.max_val!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, InRange) and self.min_val == other.min_val and self.max_val == other.max_val
