import re
from typing import Any, Callable, Sequence
import numpy as np

class Constraint:
    """Base class for all constraints."""
    def validate(self, value: Any) -> bool:
        raise NotImplementedError

    def error_message(self, value: Any) -> str:
        return f"Value {value!r} does not satisfy {self.__class__.__name__}"


class GreaterThan(Constraint):
    def __init__(self, threshold: Any):
        self.threshold = threshold

    def validate(self, value: Any) -> bool:
        return bool(value > self.threshold)

    def error_message(self, value: Any) -> str:
        return f"must be greater than {self.threshold}"


class LessThan(Constraint):
    def __init__(self, threshold: Any):
        self.threshold = threshold

    def validate(self, value: Any) -> bool:
        return bool(value < self.threshold)

    def error_message(self, value: Any) -> str:
        return f"must be less than {self.threshold}"


class InRange(Constraint):
    def __init__(self, min_val: Any, max_val: Any):
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, value: Any) -> bool:
        return bool(self.min_val <= value <= self.max_val)

    def error_message(self, value: Any) -> str:
        return f"must be in range [{self.min_val}, {self.max_val}]"


class Length(Constraint):
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


class MatchesPattern(Constraint):
    def __init__(self, pattern: str | re.Pattern[str]):
        if isinstance(pattern, str):
            self.regex = re.compile(pattern)
        else:
            self.regex = pattern

    def validate(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return bool(self.regex.match(value))

    def error_message(self, value: Any) -> str:
        return f"must match pattern {self.regex.pattern}"


class Check(Constraint):
    def __init__(self, predicate: Callable[[Any], bool], description: str | None = None):
        self.predicate = predicate
        self.description = description or getattr(predicate, "__name__", None) or "custom predicate"

    def validate(self, value: Any) -> bool:
        try:
            return bool(self.predicate(value))
        except Exception:
            return False

    def error_message(self, value: Any) -> str:
        return f"must satisfy custom check: {self.description}"


class Shape(Constraint):
    dims: tuple[int | str | None, ...]

    def __init__(self, *dims: int | str | None | Sequence[int | str | None]):
        # Support passing a sequence (like tuple or list) as the single argument
        if len(dims) == 1 and isinstance(dims[0], (tuple, list)):
            self.dims = tuple(dims[0])
        else:
            # Cast dims to sequence we can iterate on safely
            self.dims = tuple(dims)  # type: ignore

    def validate(self, value: Any) -> bool:
        if not isinstance(value, np.ndarray):
            return False
        if len(value.shape) != len(self.dims):
            return False
        for expected, actual in zip(self.dims, value.shape):
            if expected is None or expected == "*" or expected == -1:
                continue
            if isinstance(expected, str) and expected.isdigit():
                expected = int(expected)
            if expected != actual:
                return False
        return True

    def error_message(self, value: Any) -> str:
        if not isinstance(value, np.ndarray):
            return "value is not a NumPy array"
        return f"array shape {value.shape} does not match expected shape {self.dims}"


class DType(Constraint):
    def __init__(self, dtype: Any):
        self.expected_dtype = np.dtype(dtype)

    def validate(self, value: Any) -> bool:
        if not isinstance(value, np.ndarray):
            return False
        return value.dtype == self.expected_dtype

    def error_message(self, value: Any) -> str:
        if not isinstance(value, np.ndarray):
            return "value is not a NumPy array"
        return f"array dtype {value.dtype} does not match expected dtype {self.expected_dtype}"
