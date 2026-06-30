import functools
import inspect
import typing
from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin

from pydantic import TypeAdapter

from validated.exceptions import ValidationError
from validated.models import MultiValidator, Validator, ValidatorCheckError

# Lazy numpy import — the library works without numpy installed,
# array validators simply won't match non-ndarray values.
try:
    import numpy as np

    _NDARRAY_TYPE: type | None = np.ndarray
except ImportError:
    np = None  # type: ignore[assignment]
    _NDARRAY_TYPE = None


class _ParamSpec:
    """Pre-compiled validation metadata for a single parameter."""

    __slots__ = ("is_ndarray", "kind", "type_adapter", "validators")

    def __init__(
        self,
        type_adapter: TypeAdapter | None,
        validators: list[Validator],
        kind: inspect._ParameterKind,
        is_ndarray: bool,
    ):
        self.type_adapter = type_adapter
        self.validators = validators
        self.kind = kind
        self.is_ndarray = is_ndarray


def _compile_param(annotation: Any, kind: inspect._ParameterKind) -> _ParamSpec:
    """Extract base type, validators, and build a TypeAdapter at decoration time."""
    origin = get_origin(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        base_type = args[0]
        validators = []
        for m in args[1:]:
            if isinstance(m, MultiValidator):
                validators.extend(m.validators)
            elif isinstance(m, Validator):
                validators.append(m)
    else:
        base_type = annotation
        validators = []

    # Determine if this parameter should skip Pydantic coercion
    if base_type is inspect.Parameter.empty or base_type is Any:
        return _ParamSpec(None, validators, kind, is_ndarray=False)

    if _NDARRAY_TYPE is not None and (base_type is _NDARRAY_TYPE or getattr(base_type, "__name__", None) == "ndarray"):
        return _ParamSpec(None, validators, kind, is_ndarray=True)

    # Build the TypeAdapter once — this is the expensive Pydantic compilation step
    adapter = TypeAdapter(base_type)
    return _ParamSpec(adapter, validators, kind, is_ndarray=False)


def _validate_value(val: Any, spec: _ParamSpec, param_name: str) -> Any:
    """Validate and coerce a single value using pre-compiled param metadata."""
    if spec.is_ndarray:
        if _NDARRAY_TYPE is None or not isinstance(val, _NDARRAY_TYPE):
            raise ValidationError(
                parameter_name=param_name,
                value=val,
                validator=None,
                message="value is not a NumPy array",
            )
        coerced = val
    elif spec.type_adapter is not None:
        try:
            coerced = spec.type_adapter.validate_python(val)
        except Exception as e:
            raise ValidationError(
                parameter_name=param_name,
                value=val,
                validator=None,
                message=f"type validation failed: {e}",
            ) from e
    else:
        coerced = val

    # Validate custom/value validators
    errors = []
    for validator in spec.validators:
        try:
            passed = validator.validate(coerced)
            if not passed:
                errors.append(ValidationError(
                    parameter_name=param_name,
                    value=coerced,
                    validator=validator,
                    message=validator.error_message(coerced),
                ))
        except ValidatorCheckError as exc:
            # Check predicate itself raised — chain the original exception
            cause = exc.original_exception
            err = ValidationError(
                parameter_name=param_name,
                value=coerced,
                validator=validator,
                message=validator.error_message(coerced),
            )
            err.__cause__ = cause
            errors.append(err)

    if errors:
        if len(errors) == 1:
            raise errors[0]
        raise ValidationError(errors=errors)

    return coerced


def validated(func: Callable[..., Any]) -> Callable[..., Any]:
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

        errors: list[ValidationError] = []

        # Validate inputs
        for name, val in bound.arguments.items():
            if name not in param_specs:
                continue

            spec = param_specs[name]

            if spec.kind == inspect.Parameter.VAR_POSITIONAL:
                coerced_list = []
                param_has_error = False
                for idx, item in enumerate(val):
                    try:
                        coerced_item = _validate_value(item, spec, f"{name}[{idx}]")
                        coerced_list.append(coerced_item)
                    except ValidationError as exc:
                        errors.extend(exc.errors)
                        param_has_error = True
                if not param_has_error:
                    bound.arguments[name] = tuple(coerced_list)
            elif spec.kind == inspect.Parameter.VAR_KEYWORD:
                coerced_dict = {}
                param_has_error = False
                for k, v in val.items():
                    try:
                        coerced_v = _validate_value(v, spec, f"{name}[{k!r}]")
                        coerced_dict[k] = coerced_v
                    except ValidationError as exc:
                        errors.extend(exc.errors)
                        param_has_error = True
                if not param_has_error:
                    bound.arguments[name] = coerced_dict
            else:
                try:
                    coerced_val = _validate_value(val, spec, name)
                    bound.arguments[name] = coerced_val
                except ValidationError as exc:
                    errors.extend(exc.errors)

        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise ValidationError(errors=errors)

        # Call the actual function with coerced inputs
        result = func(*bound.args, **bound.kwargs)

        # Validate return value
        if return_spec is not None:
            _validate_value(result, return_spec, "<return>")

        return result

    return wrapper
