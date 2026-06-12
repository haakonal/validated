import functools
import inspect
import typing
from typing import get_origin, get_args, Annotated, Any, Callable
from pydantic import TypeAdapter
from constraints.exceptions import ConstraintValidationError
from constraints.models import Constraint
import numpy as np

def validate_value(val: Any, annotation: Any, param_name: str) -> Any:
    # 1. Check if annotation is Annotated
    origin = get_origin(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        base_type = args[0]
        # Get all instances of Constraint from metadata
        constraints = [m for m in args[1:] if isinstance(m, Constraint)]
    else:
        base_type = annotation
        constraints = []

    # Skip validation if annotation is empty or Any
    if base_type is inspect.Parameter.empty or base_type is Any:
        coerced = val
    elif base_type is np.ndarray or getattr(base_type, "__name__", None) == "ndarray":
        if not isinstance(val, np.ndarray):
            raise ConstraintValidationError(
                parameter_name=param_name,
                value=val,
                constraint=None,
                message="value is not a NumPy array"
            )
        coerced = val
    else:
        try:
            # Pydantic validation / coercion
            coerced = TypeAdapter(base_type).validate_python(val)
        except Exception as e:
            raise ConstraintValidationError(
                parameter_name=param_name,
                value=val,
                constraint=None,
                message=f"type validation failed: {e}"
            )

    # Validate custom/value constraints
    for constraint in constraints:
        if not constraint.validate(coerced):
            raise ConstraintValidationError(
                parameter_name=param_name,
                value=coerced,
                constraint=constraint,
                message=constraint.error_message(coerced)
            )

    return coerced


def constrained(func: Callable[..., Any]) -> Callable[..., Any]:
    sig = inspect.signature(func)
    
    # Get resolved type hints
    hints = {}
    try:
        hints = typing.get_type_hints(func, include_extras=True)
    except Exception:
        # Fallback to parameter annotations if get_type_hints fails (e.g. forward refs)
        for name, param in sig.parameters.items():
            if param.annotation is not inspect.Parameter.empty:
                hints[name] = param.annotation
        if sig.return_annotation is not inspect.Parameter.empty:
            hints["return"] = sig.return_annotation

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        # Validate inputs
        for name, val in bound.arguments.items():
            if name not in hints:
                continue
            
            annotation = hints[name]
            param = sig.parameters[name]

            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                coerced_list = []
                for idx, item in enumerate(val):
                    coerced_item = validate_value(item, annotation, f"{name}[{idx}]")
                    coerced_list.append(coerced_item)
                bound.arguments[name] = tuple(coerced_list)
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                coerced_dict = {}
                for k, v in val.items():
                    coerced_v = validate_value(v, annotation, f"{name}[{k!r}]")
                    coerced_dict[k] = coerced_v
                bound.arguments[name] = coerced_dict
            else:
                coerced_val = validate_value(val, annotation, name)
                bound.arguments[name] = coerced_val

        # Call the actual function with coerced inputs
        result = func(*bound.args, **bound.kwargs)

        # Validate return value
        if "return" in hints:
            validate_value(result, hints["return"], "<return>")

        return result

    return wrapper
