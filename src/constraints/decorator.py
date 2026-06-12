import functools
import inspect
import typing
from typing import get_origin, get_args, Annotated, Any, Callable
from pydantic import TypeAdapter
from constraints.exceptions import ConstraintValidationError
from constraints.models import Constraint, ConstraintCheckError

# Lazy numpy import — the library works without numpy installed,
# array constraints simply won't match non-ndarray values.
try:
    import numpy as np
    _NDARRAY_TYPE: type | None = np.ndarray
except ImportError:
    np = None  # type: ignore[assignment]
    _NDARRAY_TYPE = None


class _ParamSpec:
    """Pre-compiled validation metadata for a single parameter."""

    __slots__ = ("type_adapter", "constraints", "kind", "is_ndarray")

    def __init__(
        self,
        type_adapter: TypeAdapter | None,
        constraints: list[Constraint],
        kind: inspect._ParameterKind,
        is_ndarray: bool,
    ):
        self.type_adapter = type_adapter
        self.constraints = constraints
        self.kind = kind
        self.is_ndarray = is_ndarray


def _compile_param(annotation: Any, kind: inspect._ParameterKind) -> _ParamSpec:
    """Extract base type, constraints, and build a TypeAdapter at decoration time."""
    origin = get_origin(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        base_type = args[0]
        constraints = [m for m in args[1:] if isinstance(m, Constraint)]
    else:
        base_type = annotation
        constraints = []

    # Determine if this parameter should skip Pydantic coercion
    if base_type is inspect.Parameter.empty or base_type is Any:
        return _ParamSpec(None, constraints, kind, is_ndarray=False)

    if _NDARRAY_TYPE is not None and (
        base_type is _NDARRAY_TYPE
        or getattr(base_type, "__name__", None) == "ndarray"
    ):
        return _ParamSpec(None, constraints, kind, is_ndarray=True)

    # Build the TypeAdapter once — this is the expensive Pydantic compilation step
    adapter = TypeAdapter(base_type)
    return _ParamSpec(adapter, constraints, kind, is_ndarray=False)


def _validate_value(val: Any, spec: _ParamSpec, param_name: str) -> Any:
    """Validate and coerce a single value using pre-compiled param metadata."""
    if spec.is_ndarray:
        if _NDARRAY_TYPE is None or not isinstance(val, _NDARRAY_TYPE):
            raise ConstraintValidationError(
                parameter_name=param_name,
                value=val,
                constraint=None,
                message="value is not a NumPy array",
            )
        coerced = val
    elif spec.type_adapter is not None:
        try:
            coerced = spec.type_adapter.validate_python(val)
        except Exception as e:
            raise ConstraintValidationError(
                parameter_name=param_name,
                value=val,
                constraint=None,
                message=f"type validation failed: {e}",
            )
    else:
        coerced = val

    # Validate custom/value constraints
    for constraint in spec.constraints:
        try:
            passed = constraint.validate(coerced)
        except ConstraintCheckError as exc:
            # Check predicate itself raised — chain the original exception
            cause = exc.original_exception
            raise ConstraintValidationError(
                parameter_name=param_name,
                value=coerced,
                constraint=constraint,
                message=constraint.error_message(coerced),
            ) from cause

        if not passed:
            raise ConstraintValidationError(
                parameter_name=param_name,
                value=coerced,
                constraint=constraint,
                message=constraint.error_message(coerced),
            )

    return coerced


def constrained(func: Callable[..., Any]) -> Callable[..., Any]:
    sig = inspect.signature(func)

    # Get resolved type hints
    hints: dict[str, Any] = {}
    try:
        hints = typing.get_type_hints(func, include_extras=True)
    except Exception:
        # Fallback to parameter annotations if get_type_hints fails (e.g. forward refs)
        for name, param in sig.parameters.items():
            if param.annotation is not inspect.Parameter.empty:
                hints[name] = param.annotation
        if sig.return_annotation is not inspect.Parameter.empty:
            hints["return"] = sig.return_annotation

    # Pre-compile parameter specs at decoration time
    param_specs: dict[str, _ParamSpec] = {}
    for name, param in sig.parameters.items():
        if name not in hints:
            continue
        param_specs[name] = _compile_param(hints[name], param.kind)

    # Pre-compile return spec
    return_spec: _ParamSpec | None = None
    if "return" in hints:
        return_spec = _compile_param(hints["return"], inspect.Parameter.POSITIONAL_OR_KEYWORD)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        # Validate inputs
        for name, val in bound.arguments.items():
            if name not in param_specs:
                continue

            spec = param_specs[name]

            if spec.kind == inspect.Parameter.VAR_POSITIONAL:
                coerced_list = []
                for idx, item in enumerate(val):
                    coerced_item = _validate_value(item, spec, f"{name}[{idx}]")
                    coerced_list.append(coerced_item)
                bound.arguments[name] = tuple(coerced_list)
            elif spec.kind == inspect.Parameter.VAR_KEYWORD:
                coerced_dict = {}
                for k, v in val.items():
                    coerced_v = _validate_value(v, spec, f"{name}[{k!r}]")
                    coerced_dict[k] = coerced_v
                bound.arguments[name] = coerced_dict
            else:
                coerced_val = _validate_value(val, spec, name)
                bound.arguments[name] = coerced_val

        # Call the actual function with coerced inputs
        result = func(*bound.args, **bound.kwargs)

        # Validate return value
        if return_spec is not None:
            _validate_value(result, return_spec, "<return>")

        return result

    return wrapper
