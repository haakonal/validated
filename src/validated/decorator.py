from collections.abc import Callable
from typing import Any

from pydantic import ConfigDict, validate_call


def validated[T: Callable[..., Any]](func: T) -> T:
    """Validate function arguments and return values using Pydantic.

    Thin wrapper around @validate_call with arbitrary_types_allowed=True
    for NumPy ndarray support, and validate_return=True for return validation.
    """
    from typing import get_args, get_origin

    import numpy as np

    from validated.validators.base import Validated
    from validated.validators.numpy import DType

    for k, v in getattr(func, "__annotations__", {}).items():
        origin = get_origin(v)
        if origin is np.ndarray:
            args = get_args(v)
            if len(args) == 2:
                dtype_arg = args[1]
                if get_origin(dtype_arg) is np.dtype:
                    target_dtype = get_args(dtype_arg)[0]
                else:
                    target_dtype = dtype_arg
                func.__annotations__[k] = Validated[np.ndarray, DType(target_dtype)]

    # Use validate_call to create the decorator
    decorator = validate_call(
        config=ConfigDict(arbitrary_types_allowed=True),
        validate_return=True,
    )
    return decorator(func)  # type: ignore
