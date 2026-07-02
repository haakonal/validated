from collections.abc import Sequence
from typing import Any

import numpy as np

from validated.validators.base import Validator


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
