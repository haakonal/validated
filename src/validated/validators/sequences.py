from typing import Any

from validated.validators.base import Validator


class Length(Validator):
    def __init__(self, min_len: int | None = None, max_len: int | None = None):
        self.min_len = min_len
        self.max_len = max_len

    def validate(self, value: Any) -> bool:
        try:
            length = len(value)
        except TypeError:
            return False
        if self.min_len is not None and length < self.min_len:
            return False
        if self.max_len is not None and length > self.max_len:
            return False
        return True

    def error_message(self, value: Any) -> str:
        if self.min_len is not None and self.max_len is not None:
            return f"length must be between {self.min_len} and {self.max_len}"
        if self.min_len is not None:
            return f"length must be at least {self.min_len}"
        if self.max_len is not None:
            return f"length must be at most {self.max_len}"
        return "invalid length"

    def __repr__(self) -> str:
        return f"Length(min_len={self.min_len!r}, max_len={self.max_len!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Length) and self.min_len == other.min_len and self.max_len == other.max_len


class NonEmpty(Length):
    """Shortcut for Length(min_len=1)."""

    def __init__(self):
        super().__init__(min_len=1)

    def error_message(self, value: Any) -> str:
        return "must not be empty"

    def __repr__(self) -> str:
        return "NonEmpty()"


class Contains(Validator):
    def __init__(self, item: Any):
        self.item = item

    def validate(self, value: Any) -> bool:
        try:
            return self.item in value
        except TypeError:
            return False

    def error_message(self, value: Any) -> str:
        return f"must contain {self.item!r}"

    def __repr__(self) -> str:
        return f"Contains(item={self.item!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Contains) and self.item == other.item


class Unique(Validator):
    def validate(self, value: Any) -> bool:
        try:
            return len(value) == len(set(value))
        except TypeError:
            # If elements are unhashable, fallback to slow O(n^2) check
            seen = []
            try:
                for item in value:
                    if item in seen:
                        return False
                    seen.append(item)
                return True
            except TypeError:
                return False

    def error_message(self, value: Any) -> str:
        return "all elements must be unique"

    def __repr__(self) -> str:
        return "Unique()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Unique)


class Sorted(Validator):
    def __init__(self, reverse: bool = False):
        self.reverse = reverse

    def validate(self, value: Any) -> bool:
        try:
            it = iter(value)
            try:
                prev = next(it)
            except StopIteration:
                return True

            for current in it:
                if self.reverse:
                    if current > prev:
                        return False
                else:
                    if current < prev:
                        return False
                prev = current
            return True
        except TypeError:
            return False

    def error_message(self, value: Any) -> str:
        order = "descending" if self.reverse else "ascending"
        return f"elements must be in {order} order"

    def __repr__(self) -> str:
        return f"Sorted(reverse={self.reverse})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Sorted) and self.reverse == other.reverse
