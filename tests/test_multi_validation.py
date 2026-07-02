import pytest
from pydantic import ValidationError

from validated import (
    GreaterThan,
    InRange,
    LessThan,
    Validated,
    validated,
)


def test_single_parameter_failure_compatibility() -> None:
    @validated
    def func(a: Validated[int, GreaterThan(0)]):
        return a

    with pytest.raises(ValidationError) as excinfo:
        func(-5)

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == (0,)
    assert errors[0]["input"] == -5
    assert "must be greater than 0" in errors[0]["msg"]


def test_multiple_parameter_failures() -> None:
    @validated
    def func(
        a: Validated[int, GreaterThan(0)],
        b: Validated[float, LessThan(0.0)],
        c: Validated[float, InRange(0.0, 100.0)],
    ):
        return a, b, c

    with pytest.raises(ValidationError) as excinfo:
        func(a=-1, b=5.0, c=150.0)

    # All three fail validation
    errs = excinfo.value.errors()
    assert len(errs) == 3

    assert errs[0]["loc"] == ("a",)
    assert errs[0]["input"] == -1
    assert "must be greater than 0" in errs[0]["msg"]

    assert errs[1]["loc"] == ("b",)
    assert errs[1]["input"] == 5.0
    assert "must be less than 0.0" in errs[1]["msg"]

    assert errs[2]["loc"] == ("c",)
    assert errs[2]["input"] == 150.0
    assert "must be in range [0.0, 100.0]" in errs[2]["msg"]


def test_multiple_var_positional_failures() -> None:
    @validated
    def func(*items: Validated[int, GreaterThan(0)]):
        return items

    with pytest.raises(ValidationError) as excinfo:
        func(5, -1, 10, -3)

    errs = excinfo.value.errors()
    assert len(errs) == 2

    assert errs[0]["loc"] == (1,)
    assert errs[0]["input"] == -1
    assert "must be greater than 0" in errs[0]["msg"]

    assert errs[1]["loc"] == (3,)
    assert errs[1]["input"] == -3
    assert "must be greater than 0" in errs[1]["msg"]


def test_multiple_var_keyword_failures() -> None:
    @validated
    def func(**options: Validated[float, InRange(0.0, 1.0)]):
        return options

    # Pass multiple invalid kwargs
    with pytest.raises(ValidationError) as excinfo:
        func(alpha=-0.5, beta=1.5, gamma=0.5)

    errs = excinfo.value.errors()
    assert len(errs) == 2

    # Options ordering
    param_names = [e["loc"] for e in errs]
    assert ("alpha",) in param_names
    assert ("beta",) in param_names

    values = [e["input"] for e in errs]
    assert -0.5 in values
    assert 1.5 in values


def test_mixed_parameter_failures() -> None:
    @validated
    def func(
        x: Validated[int, GreaterThan(10)],
        *args: Validated[int, LessThan(0)],
        y: Validated[float, InRange(0.0, 1.0)] = 0.5,
        **kwargs: Validated[str, InRange("a", "m")],  # String InRange comparison
    ):
        return x, args, y, kwargs

    with pytest.raises(ValidationError) as excinfo:
        func(5, -1, 2, z="z")

    errs = excinfo.value.errors()
    assert len(errs) == 3

    assert errs[0]["loc"] == (0,)
    assert errs[0]["input"] == 5

    assert errs[1]["loc"] == (2,)
    assert errs[1]["input"] == 2

    assert errs[2]["loc"] == ("z",)
    assert errs[2]["input"] == "z"
