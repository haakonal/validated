from typing import Annotated

import pytest

from validated import (
    GreaterThan,
    InRange,
    LessThan,
    ValidationError,
    validated,
)


def test_single_parameter_failure_compatibility():
    @validated
    def func(a: Annotated[int, GreaterThan(0)]):
        return a

    with pytest.raises(ValidationError) as excinfo:
        func(-5)

    assert excinfo.value.parameter_name == "a"
    assert excinfo.value.value == -5
    assert isinstance(excinfo.value.validator, GreaterThan)
    assert "must be greater than 0" in excinfo.value.message
    assert len(excinfo.value.errors) == 1
    assert excinfo.value.errors[0] is excinfo.value


def test_multiple_parameter_failures():
    @validated
    def func(
        a: Annotated[int, GreaterThan(0)],
        b: Annotated[float, LessThan(0.0)],
        c: Annotated[float, InRange(0.0, 100.0)],
    ):
        return a, b, c

    with pytest.raises(ValidationError) as excinfo:
        func(a=-1, b=5.0, c=150.0)

    # All three fail validation
    errs = excinfo.value.errors
    assert len(errs) == 3

    assert errs[0].parameter_name == "a"
    assert errs[0].value == -1
    assert isinstance(errs[0].validator, GreaterThan)

    assert errs[1].parameter_name == "b"
    assert errs[1].value == 5.0
    assert isinstance(errs[1].validator, LessThan)

    assert errs[2].parameter_name == "c"
    assert errs[2].value == 150.0
    assert isinstance(errs[2].validator, InRange)

    # Primary fields on the group exception should reflect the first error
    assert excinfo.value.parameter_name == "a"
    assert excinfo.value.value == -1

    # Exception message should summarize all of them
    msg = str(excinfo.value)
    assert "Validation failed for multiple parameters:" in msg
    assert "- a: must be greater than 0" in msg
    assert "- b: must be less than 0.0" in msg
    assert "- c: must be in range [0.0, 100.0]" in msg


def test_multiple_var_positional_failures():
    @validated
    def func(*items: Annotated[int, GreaterThan(0)]):
        return items

    with pytest.raises(ValidationError) as excinfo:
        func(5, -1, 10, -3)

    errs = excinfo.value.errors
    assert len(errs) == 2

    assert errs[0].parameter_name == "items[1]"
    assert errs[0].value == -1

    assert errs[1].parameter_name == "items[3]"
    assert errs[1].value == -3

    # Primary fields should reflect first error
    assert excinfo.value.parameter_name == "items[1]"
    assert excinfo.value.value == -1


def test_multiple_var_keyword_failures():
    @validated
    def func(**options: Annotated[float, InRange(0.0, 1.0)]):
        return options

    # Pass multiple invalid kwargs
    with pytest.raises(ValidationError) as excinfo:
        func(alpha=-0.5, beta=1.5, gamma=0.5)

    errs = excinfo.value.errors
    assert len(errs) == 2

    # Ordering is determined by iteration order of kwargs dict
    param_names = [e.parameter_name for e in errs]
    assert "options['alpha']" in param_names
    assert "options['beta']" in param_names

    values = [e.value for e in errs]
    assert -0.5 in values
    assert 1.5 in values


def test_mixed_parameter_failures():
    @validated
    def func(
        x: Annotated[int, GreaterThan(10)],
        *args: Annotated[int, LessThan(0)],
        y: Annotated[float, InRange(0.0, 1.0)] = 0.5,
        **kwargs: Annotated[str, InRange("a", "m")],  # String InRange comparison
    ):
        return x, args, y, kwargs

    # x fails (value 5 <= 10)
    # args[1] fails (value 2 >= 0)
    # kwargs['z'] fails (value 'z' > 'm')
    with pytest.raises(ValidationError) as excinfo:
        func(5, -1, 2, z="z")

    errs = excinfo.value.errors
    assert len(errs) == 3

    assert errs[0].parameter_name == "x"
    assert errs[0].value == 5

    assert errs[1].parameter_name == "args[1]"
    assert errs[1].value == 2

    assert errs[2].parameter_name == "kwargs['z']"
    assert errs[2].value == "z"
