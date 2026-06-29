# from pydantic import PydanticSchemaGenerationError
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class ValidatorBaseModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True)


class Validator(ABC):
    """Base class for all validators."""

    @abstractmethod
    def validate(self, value: Any) -> bool: ...

    def error_message(self, value: Any) -> str:
        return f"Value {value!r} does not satisfy {self.__class__.__name__}"

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        """Hook into Pydantic v2 so this validator works as Annotated metadata on BaseModel fields."""
        schema = handler(source_type)

        def _after_validate(value: Any) -> Any:
            if not self.validate(value):
                raise ValueError(self.error_message(value))
            return value

        return core_schema.no_info_after_validator_function(_after_validate, schema)


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


class MatchesPattern(Validator):
    def __init__(self, pattern: str | re.Pattern[str]):
        if isinstance(pattern, str):
            self.regex = re.compile(pattern)
        else:
            self.regex = pattern

    def validate(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return bool(self.regex.fullmatch(value))

    def error_message(self, value: Any) -> str:
        return f"must match pattern {self.regex.pattern}"

    def __repr__(self) -> str:
        return f"MatchesPattern(pattern={self.regex.pattern!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MatchesPattern) and self.regex.pattern == other.regex.pattern


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


class ValidatorCheckError(Exception):
    """Raised when a Check predicate itself throws an exception during evaluation."""

    def __init__(self, message: str, original_exception: Exception):
        super().__init__(message)
        self.original_exception = original_exception


class Shape(Validator):
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
        for expected, actual in zip(self.dims, value.shape, strict=False):
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

    def __repr__(self) -> str:
        return f"Shape(dims={self.dims!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Shape) and self.dims == other.dims


class DType(Validator):
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

    def __repr__(self) -> str:
        return f"DType(dtype={self.expected_dtype!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DType) and self.expected_dtype == other.expected_dtype
