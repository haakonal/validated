import numpy as np
import pytest
from pydantic import ValidationError

from validated.validators.base import ValidatorBaseModel


def test_regular_ndarray():
    class MyModel(ValidatorBaseModel):
        arr: np.ndarray

    m = MyModel(arr=np.array([1, 2]))
    assert isinstance(m.arr, np.ndarray)

    with pytest.raises(ValidationError):
        MyModel(arr=[1, 2])
