import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from validated.validators.base import Validated, ValidatorBaseModel
from validated.validators.numpy import DType, Shape


def test_ndarray_in_model():
    class MyModel(ValidatorBaseModel):
        arr: NDArray[np.float64]

    # Valid array
    m = MyModel(arr=np.array([1.0, 2.0], dtype=np.float64))
    assert np.array_equal(m.arr, np.array([1.0, 2.0], dtype=np.float64))

    # Invalid array dtype
    with pytest.raises(ValidationError) as excinfo:
        MyModel(arr=np.array([1, 2], dtype=np.int32))

    errors = excinfo.value.errors()
    assert "does not match expected dtype float64" in errors[0]["msg"]


def test_comprehensive_ndarray_combinations():
    class MyModel(ValidatorBaseModel):
        # 1. Native numpy array (arbitrary types allowed)
        arr1: np.ndarray

        # 2. NDArray with dtype
        arr2: NDArray[np.float64]

        # 3. Explicit Validated wrapper with np.ndarray base
        arr3: Validated[np.ndarray, Shape(2), DType(np.int32)]

        # 4. NDArray nested inside Validated wrapper
        arr4: Validated[NDArray[np.float64], Shape(2)]

    # All valid
    m1 = MyModel(
        arr1=np.array(["a"]),
        arr2=np.array([1.0], dtype=np.float64),
        arr3=np.array([1, 2], dtype=np.int32),
        arr4=np.array([1.0, 2.0], dtype=np.float64),
    )
    assert m1 is not None

    # Invalid arr3 (shape)
    with pytest.raises(ValidationError) as exc:
        MyModel(
            arr1=np.array(["a"]),
            arr2=np.array([1.0], dtype=np.float64),
            arr3=np.array([1, 2, 3], dtype=np.int32),
            arr4=np.array([1.0, 2.0], dtype=np.float64),
        )
    assert "array shape" in str(exc.value)

    # Invalid arr4 (dtype)
    with pytest.raises(ValidationError) as exc:
        MyModel(
            arr1=np.array(["a"]),
            arr2=np.array([1.0], dtype=np.float64),
            arr3=np.array([1, 2], dtype=np.int32),
            arr4=np.array([1, 2], dtype=np.int32),  # wrong dtype
        )
    assert "expected dtype float64" in str(exc.value)

    # Invalid arr4 (shape)
    with pytest.raises(ValidationError) as exc:
        MyModel(
            arr1=np.array(["a"]),
            arr2=np.array([1.0], dtype=np.float64),
            arr3=np.array([1, 2], dtype=np.int32),
            arr4=np.array([1.0, 2.0, 3.0], dtype=np.float64),  # wrong shape
        )
    assert "expected shape (2,)" in str(exc.value)
