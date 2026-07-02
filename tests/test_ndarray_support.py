import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from validated import (
    Validated,
    validated,
)
from validated.validators.numpy import DType, Shape


def test_ndarray_type_alias():
    @validated
    def process(arr: Validated[NDArray[np.float64], DType(np.float64)]):
        return arr

    a = np.array([1.0, 2.0], dtype=np.float64)
    assert np.array_equal(process(a), a)

    with pytest.raises(ValidationError) as excinfo:
        process(np.array([1, 2], dtype=np.int32))

    err_str = str(excinfo.value)
    assert "array dtype int32 does not match expected dtype float64" in err_str


def test_ndarray_string_dtype():
    @validated
    def process(arr: Validated[NDArray[np.float32], DType(np.float32)]):
        return arr

    a = np.array([1.0, 2.0], dtype=np.float32)
    assert np.array_equal(process(a), a)

    with pytest.raises(ValidationError) as excinfo:
        process(np.array([1, 2], dtype=np.int32))

    err_str = str(excinfo.value)
    assert "array dtype int32 does not match expected dtype float32" in err_str


def test_numpy_coverage():
    s = Shape(3)
    assert not s.validate("not an array")
    assert s.error_message("not an array") == "value is not a NumPy array"

    d = DType(np.float64)
    assert not d.validate("not an array")
    assert d.error_message("not an array") == "value is not a NumPy array"
