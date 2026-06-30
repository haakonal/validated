"""Tests to verify:
1. Check() works with multi-parameter error collection
2. Multiple validators in a single Annotated[] work correctly
"""

from typing import Annotated

import pytest

from validated import (
    Check,
    GreaterThan,
    LessThan,
    ValidationError,
    validated,
)

# ── Scenario 1: Check() with multi-parameter error collection ──────────


def test_check_multi_param_returning_false():
    """Two params both using Check() that returns False — errors should be collected."""

    @validated
    def func(
        a: Annotated[int, Check(lambda v: v > 0, "must be positive")],
        b: Annotated[int, Check(lambda v: v % 2 == 0, "must be even")],
    ):
        return a, b

    # Both fail
    with pytest.raises(ValidationError) as excinfo:
        func(-1, 3)

    errs = excinfo.value.errors
    assert len(errs) == 2, f"Expected 2 errors, got {len(errs)}: {errs}"

    assert errs[0].parameter_name == "a"
    assert isinstance(errs[0].validator, Check)
    assert "must be positive" in errs[0].message

    assert errs[1].parameter_name == "b"
    assert isinstance(errs[1].validator, Check)
    assert "must be even" in errs[1].message


def test_check_multi_param_raising_exception():
    """Two params both using Check() where the predicate raises — errors should be collected."""

    def needs_len(v):
        return len(v) > 0  # will raise TypeError on int

    @validated
    def func(
        a: Annotated[int, Check(needs_len, "needs length")],
        b: Annotated[int, Check(needs_len, "needs length")],
    ):
        return a, b

    with pytest.raises(ValidationError) as excinfo:
        func(42, 99)

    errs = excinfo.value.errors
    assert len(errs) == 2, f"Expected 2 errors, got {len(errs)}: {errs}"

    assert errs[0].parameter_name == "a"
    assert isinstance(errs[0].validator, Check)
    assert errs[0].__cause__ is not None  # original exception chained

    assert errs[1].parameter_name == "b"
    assert isinstance(errs[1].validator, Check)
    assert errs[1].__cause__ is not None


def test_check_mixed_with_builtin_validators_multi_param():
    """Mix of Check() and built-in validators across params, all failing."""

    @validated
    def func(
        a: Annotated[int, Check(lambda v: v > 0, "must be positive")],
        b: Annotated[float, LessThan(0.0)],
        c: Annotated[int, Check(lambda v: v % 2 == 0, "must be even")],
    ):
        return a, b, c

    with pytest.raises(ValidationError) as excinfo:
        func(-1, 5.0, 3)

    errs = excinfo.value.errors
    assert len(errs) == 3, f"Expected 3 errors, got {len(errs)}: {errs}"

    assert errs[0].parameter_name == "a"
    assert isinstance(errs[0].validator, Check)

    assert errs[1].parameter_name == "b"
    assert isinstance(errs[1].validator, LessThan)

    assert errs[2].parameter_name == "c"
    assert isinstance(errs[2].validator, Check)


# ── Scenario 2: Multiple validators in one Annotated[] ─────────────────


def test_multiple_validators_single_param_first_fails():
    """Annotated with two validators; the first one fails."""

    @validated
    def func(x: Annotated[int, GreaterThan(0), LessThan(100)]):
        return x

    with pytest.raises(ValidationError) as excinfo:
        func(-5)

    assert excinfo.value.parameter_name == "x"
    assert isinstance(excinfo.value.validator, GreaterThan)
    assert "must be greater than 0" in excinfo.value.message


def test_multiple_validators_single_param_second_fails():
    """Annotated with two validators; value passes first, fails second."""

    @validated
    def func(x: Annotated[int, GreaterThan(0), LessThan(100)]):
        return x

    with pytest.raises(ValidationError) as excinfo:
        func(150)

    assert excinfo.value.parameter_name == "x"
    assert isinstance(excinfo.value.validator, LessThan)
    assert "must be less than 100" in excinfo.value.message


def test_multiple_validators_single_param_both_pass():
    """Annotated with two validators; value satisfies both."""

    @validated
    def func(x: Annotated[int, GreaterThan(0), LessThan(100)]):
        return x

    assert func(50) == 50


def test_multiple_validators_single_param_both_fail():
    """Annotated with two validators; value fails both and both errors are reported."""

    @validated
    def func(x: Annotated[int, GreaterThan(10), LessThan(5)]):
        return x

    # value 7: fails GreaterThan(10) and LessThan(5)
    with pytest.raises(ValidationError) as excinfo:
        func(7)

    errs = excinfo.value.errors
    assert len(errs) == 2
    assert errs[0].parameter_name == "x"
    assert isinstance(errs[0].validator, GreaterThan)
    assert errs[1].parameter_name == "x"
    assert isinstance(errs[1].validator, LessThan)


def test_multiple_validators_with_check_in_annotated():
    """Mix of built-in and Check() validators on one parameter."""

    @validated
    def func(
        x: Annotated[int, GreaterThan(0), Check(lambda v: v % 2 == 0, "must be even")],
    ):
        return x

    # Passes both
    assert func(4) == 4

    # Fails GreaterThan
    with pytest.raises(ValidationError) as excinfo:
        func(-2)
    assert isinstance(excinfo.value.validator, GreaterThan)

    # Passes GreaterThan, fails Check
    with pytest.raises(ValidationError) as excinfo:
        func(3)
    assert isinstance(excinfo.value.validator, Check)
    assert "must be even" in excinfo.value.message


def test_multiple_validators_multi_param_error_collection():
    """Two params each with multiple validators — errors collected across params,
    but only first-failing validator per param."""

    @validated
    def func(
        x: Annotated[int, GreaterThan(0), LessThan(100)],
        y: Annotated[int, GreaterThan(10), LessThan(50)],
    ):
        return x, y

    # x fails GreaterThan(0), y fails GreaterThan(10)
    with pytest.raises(ValidationError) as excinfo:
        func(-5, 5)

    errs = excinfo.value.errors
    assert len(errs) == 2

    assert errs[0].parameter_name == "x"
    assert isinstance(errs[0].validator, GreaterThan)

    assert errs[1].parameter_name == "y"
    assert isinstance(errs[1].validator, GreaterThan)


def test_check_in_var_positional_multi_errors():
    """Check() validator on *args with multiple failures."""

    @validated
    def func(*items: Annotated[int, Check(lambda v: v > 0, "must be positive")]):
        return items

    with pytest.raises(ValidationError) as excinfo:
        func(1, -2, 3, -4)

    errs = excinfo.value.errors
    assert len(errs) == 2

    assert errs[0].parameter_name == "items[1]"
    assert errs[0].value == -2

    assert errs[1].parameter_name == "items[3]"
    assert errs[1].value == -4


def test_check_in_var_keyword_multi_errors():
    """Check() validator on **kwargs with multiple failures."""

    @validated
    def func(
        **opts: Annotated[str, Check(lambda v: v.startswith("x"), "must start with x")],
    ):
        return opts

    with pytest.raises(ValidationError) as excinfo:
        func(a="xfoo", b="bar", c="xbaz", d="qux")

    errs = excinfo.value.errors
    assert len(errs) == 2

    param_names = [e.parameter_name for e in errs]
    assert "opts['b']" in param_names
    assert "opts['d']" in param_names
