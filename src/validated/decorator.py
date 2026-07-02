from collections.abc import Callable
from typing import Any

from pydantic import ConfigDict, validate_call


def validated[T: Callable[..., Any]](func: T) -> T:
    """Validate function arguments and return values using Pydantic.

    Thin wrapper around @validate_call with arbitrary_types_allowed=True
    for NumPy ndarray support, and validate_return=True for return validation.
    """
    # Use validate_call to create the decorator
    decorator = validate_call(
        config=ConfigDict(arbitrary_types_allowed=True),
        validate_return=True,
    )
    return decorator(func)  # type: ignore
