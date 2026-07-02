"""Tests to verify:
1. Check() works with multi-parameter error collection
2. Multiple validators in a single Validated[] work correctly
"""

import pytest
from pydantic import ValidationError

from validated import (
    Check,
    GreaterThan,
    LessThan,
    Validated,
    validated,
)

# ── Scenario 1: Check() with multi-parameter error collection ──────────


def test_check_multi_param_returning_false() -> None:
    """Two params both using Check() that returns False — errors should be collected."""

    @validated
    def func(
        a: Validated[int, Check(lambda v: v > 0, "must be positive")],
        b: Validated[int, Check(lambda v: v % 2 == 0, "must be even")],
    ):
        return a, b

    # Both fail
    with pytest.raises(ValidationError) as excinfo:
        func(-1, 3)

    errs = excinfo.value.errors()
    assert len(errs) == 2, f"Expected 2 errors, got {len(errs)}: {errs}"

    assert errs[0]["loc"] == (0,)
    assert "must be positive" in errs[0]["msg"]

    assert errs[1]["loc"] == (1,)
    assert "must be even" in errs[1]["msg"]


def test_check_multi_param_raising_exception() -> None:
    """Two params both using Check() where the predicate raises — errors should be collected."""

    def needs_len(v):
        return len(v) > 0  # will raise TypeError on int

    @validated
    def func(
        a: Validated[int, Check(needs_len, "needs length")],
        b: Validated[int, Check(needs_len, "needs length")],
    ):
        return a, b

    with pytest.raises(ValidationError) as excinfo:
        func(42, 99)

    errs = excinfo.value.errors()
    assert len(errs) == 2, f"Expected 2 errors, got {len(errs)}: {errs}"

    assert errs[0]["loc"] == (0,)
    assert "TypeError" in errs[0]["msg"]

    assert errs[1]["loc"] == (1,)
    assert "TypeError" in errs[1]["msg"]


def test_check_mixed_with_builtin_validators_multi_param() -> None:
    """Mix of Check() and built-in validators across params, all failing."""

    @validated
    def func(
        a: Validated[int, Check(lambda v: v > 0, "must be positive")],
        b: Validated[float, LessThan(0.0)],
        c: Validated[int, Check(lambda v: v % 2 == 0, "must be even")],
    ):
        return a, b, c

    with pytest.raises(ValidationError) as excinfo:
        func(-1, 5.0, 3)

    errs = excinfo.value.errors()
    assert len(errs) == 3, f"Expected 3 errors, got {len(errs)}: {errs}"

    assert errs[0]["loc"] == (0,)
    assert "must be positive" in errs[0]["msg"]

    assert errs[1]["loc"] == (1,)
    assert "must be less than 0.0" in errs[1]["msg"]

    assert errs[2]["loc"] == (2,)
    assert "must be even" in errs[2]["msg"]


# ── Scenario 2: Multiple validators in one Validated[] ─────────────────


def test_multiple_validators_single_param_first_fails() -> None:
    """Validated with two validators; the first one fails."""

    @validated
    def func(x: Validated[int, GreaterThan(0), LessThan(100)]):
        return x

    with pytest.raises(ValidationError) as excinfo:
        func(-5)

    errs = excinfo.value.errors()
    assert errs[0]["loc"] == (0,)
    assert "must be greater than 0" in errs[0]["msg"]


def test_multiple_validators_single_param_second_fails() -> None:
    """Validated with two validators; value passes first, fails second."""

    @validated
    def func(x: Validated[int, GreaterThan(0), LessThan(100)]):
        return x

    with pytest.raises(ValidationError) as excinfo:
        func(150)

    errs = excinfo.value.errors()
    assert errs[0]["loc"] == (0,)
    assert "must be less than 100" in errs[0]["msg"]


def test_multiple_validators_single_param_both_pass() -> None:
    """Validated with two validators; value satisfies both."""

    @validated
    def func(x: Validated[int, GreaterThan(0), LessThan(100)]):
        return x

    assert func(50) == 50


def test_multiple_validators_single_param_both_fail() -> None:
    """Validated with two validators; value fails both and both errors are reported."""

    @validated
    def func(x: Validated[int, GreaterThan(10), LessThan(5)]):
        return x

    # value 7: fails GreaterThan(10) and LessThan(5)
    with pytest.raises(ValidationError) as excinfo:
        func(7)

    errs = excinfo.value.errors()
    # Pydantic receives ValueError with multiple lines from MultiValidator
    assert len(errs) == 1
    msg = errs[0]["msg"]
    assert "must be greater than 10" in msg
    assert "must be less than 5" in msg


def test_multiple_validators_with_check_in_validated() -> None:
    """Mix of built-in and Check() validators on one parameter."""

    @validated
    def func(
        x: Validated[int, GreaterThan(0), Check(lambda v: v % 2 == 0, "must be even")],
    ):
        return x

    # Passes both
    assert func(4) == 4

    # Fails GreaterThan
    with pytest.raises(ValidationError) as excinfo:
        func(-2)
    assert "must be greater than 0" in excinfo.value.errors()[0]["msg"]

    # Passes GreaterThan, fails Check
    with pytest.raises(ValidationError) as excinfo:
        func(3)
    assert "must be even" in excinfo.value.errors()[0]["msg"]


def test_multiple_validators_multi_param_error_collection() -> None:
    """Two params each with multiple validators — errors collected across params."""

    @validated
    def func(
        x: Validated[int, GreaterThan(0), LessThan(100)],
        y: Validated[int, GreaterThan(10), LessThan(50)],
    ):
        return x, y

    # x fails GreaterThan(0), y fails GreaterThan(10)
    with pytest.raises(ValidationError) as excinfo:
        func(-5, 5)

    errs = excinfo.value.errors()
    assert len(errs) == 2

    assert errs[0]["loc"] == (0,)
    assert "must be greater than 0" in errs[0]["msg"]

    assert errs[1]["loc"] == (1,)
    assert "must be greater than 10" in errs[1]["msg"]


def test_check_in_var_positional_multi_errors() -> None:
    """Check() validator on *args with multiple failures."""

    @validated
    def func(*items: Validated[int, Check(lambda v: v > 0, "must be positive")]):
        return items

    with pytest.raises(ValidationError) as excinfo:
        func(1, -2, 3, -4)

    errs = excinfo.value.errors()
    assert len(errs) == 2

    assert errs[0]["loc"] == (1,)
    assert errs[0]["input"] == -2

    assert errs[1]["loc"] == (3,)
    assert errs[1]["input"] == -4


def test_check_in_var_keyword_multi_errors() -> None:
    """Check() validator on **kwargs with multiple failures."""

    @validated
    def func(
        **opts: Validated[str, Check(lambda v: v.startswith("x"), "must start with x")],
    ):
        return opts

    with pytest.raises(ValidationError) as excinfo:
        func(a="xfoo", b="bar", c="xbaz", d="qux")

    errs = excinfo.value.errors()
    assert len(errs) == 2

    param_names = [e["loc"] for e in errs]
    assert ("b",) in param_names
    assert ("d",) in param_names
