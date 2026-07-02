import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ConfigDict, ValidationError

from validated.validators.base import ValidatorBaseModel


def test_ndarray_in_model():
    class MyModel(ValidatorBaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)
        arr: NDArray[np.float64]

    # Valid array
    m = MyModel(arr=np.array([1.0, 2.0], dtype=np.float64))
    assert np.array_equal(m.arr, np.array([1.0, 2.0], dtype=np.float64))

    # Invalid array dtype
    with pytest.raises(ValidationError) as excinfo:
        MyModel(arr=np.array([1, 2], dtype=np.int32))

    errors = excinfo.value.errors()
    assert "does not match expected dtype float64" in errors[0]["msg"]
