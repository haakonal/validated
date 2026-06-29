"""Direct verification script — no pytest, pure assertions."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from typing import Annotated

from validated import (
    Check,
    GreaterThan,
    LessThan,
    ValidationError,
    validated,
)

passed = 0
failed = 0


def run_test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  PASS: {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"        {type(e).__name__}: {e}")
        failed += 1


# ── Scenario 1: Check() with multi-parameter error collection ──────────


def test_check_multi_param_returning_false():
    @validated
    def func(
        a: Annotated[int, Check(lambda v: v > 0, "must be positive")],
        b: Annotated[int, Check(lambda v: v % 2 == 0, "must be even")],
    ):
        return a, b

    try:
        func(-1, 3)
        raise AssertionError("Should have raised")
    except ValidationError as e:
        errs = e.errors
        assert len(errs) == 2, f"Expected 2 errors, got {len(errs)}"
        assert errs[0].parameter_name == "a"
        assert isinstance(errs[0].validator, Check)
        assert "must be positive" in errs[0].message
        assert errs[1].parameter_name == "b"
        assert isinstance(errs[1].validator, Check)
        assert "must be even" in errs[1].message


def test_check_multi_param_raising_exception():
    def needs_len(v):
        return len(v) > 0  # raises TypeError on int

    @validated
    def func(
        a: Annotated[int, Check(needs_len, "needs length")],
        b: Annotated[int, Check(needs_len, "needs length")],
    ):
        return a, b

    try:
        func(42, 99)
        raise AssertionError("Should have raised")
    except ValidationError as e:
        errs = e.errors
        assert len(errs) == 2, f"Expected 2 errors, got {len(errs)}"
        assert errs[0].parameter_name == "a"
        assert isinstance(errs[0].validator, Check)
        assert errs[0].__cause__ is not None, "Expected chained cause for a"
        assert errs[1].parameter_name == "b"
        assert isinstance(errs[1].validator, Check)
        assert errs[1].__cause__ is not None, "Expected chained cause for b"


def test_check_mixed_with_builtin_multi_param():
    @validated
    def func(
        a: Annotated[int, Check(lambda v: v > 0, "must be positive")],
        b: Annotated[float, LessThan(0.0)],
        c: Annotated[int, Check(lambda v: v % 2 == 0, "must be even")],
    ):
        return a, b, c

    try:
        func(-1, 5.0, 3)
        raise AssertionError("Should have raised")
    except ValidationError as e:
        errs = e.errors
        assert len(errs) == 3, f"Expected 3 errors, got {len(errs)}"
        assert errs[0].parameter_name == "a"
        assert isinstance(errs[0].validator, Check)
        assert errs[1].parameter_name == "b"
        assert isinstance(errs[1].validator, LessThan)
        assert errs[2].parameter_name == "c"
        assert isinstance(errs[2].validator, Check)


# ── Scenario 2: Multiple validators in one Annotated[] ─────────────────


def test_multi_validators_first_fails():
    @validated
    def func(x: Annotated[int, GreaterThan(0), LessThan(100)]):
        return x

    try:
        func(-5)
        raise AssertionError("Should have raised")
    except ValidationError as e:
        assert e.parameter_name == "x"
        assert isinstance(e.validator, GreaterThan)
        assert "must be greater than 0" in e.message


def test_multi_validators_second_fails():
    @validated
    def func(x: Annotated[int, GreaterThan(0), LessThan(100)]):
        return x

    try:
        func(150)
        raise AssertionError("Should have raised")
    except ValidationError as e:
        assert e.parameter_name == "x"
        assert isinstance(e.validator, LessThan)
        assert "must be less than 100" in e.message


def test_multi_validators_both_pass():
    @validated
    def func(x: Annotated[int, GreaterThan(0), LessThan(100)]):
        return x

    assert func(50) == 50


def test_multi_validators_both_fail_short_circuits():
    """When both validators fail, only the first one is reported (short-circuit)."""

    @validated
    def func(x: Annotated[int, GreaterThan(10), LessThan(5)]):
        return x

    try:
        func(7)
        raise AssertionError("Should have raised")
    except ValidationError as e:
        assert e.parameter_name == "x"
        assert isinstance(e.validator, GreaterThan)


def test_multi_validators_with_check():
    @validated
    def func(
        x: Annotated[int, GreaterThan(0), Check(lambda v: v % 2 == 0, "must be even")],
    ):
        return x

    assert func(4) == 4

    try:
        func(-2)
        raise AssertionError("Should have raised")
    except ValidationError as e:
        assert isinstance(e.validator, GreaterThan)

    try:
        func(3)
        raise AssertionError("Should have raised")
    except ValidationError as e:
        assert isinstance(e.validator, Check)
        assert "must be even" in e.message


def test_multi_validators_multi_param_error_collection():
    @validated
    def func(
        x: Annotated[int, GreaterThan(0), LessThan(100)],
        y: Annotated[int, GreaterThan(10), LessThan(50)],
    ):
        return x, y

    try:
        func(-5, 5)
        raise AssertionError("Should have raised")
    except ValidationError as e:
        errs = e.errors
        assert len(errs) == 2, f"Expected 2 errors, got {len(errs)}"
        assert errs[0].parameter_name == "x"
        assert isinstance(errs[0].validator, GreaterThan)
        assert errs[1].parameter_name == "y"
        assert isinstance(errs[1].validator, GreaterThan)


def test_check_in_var_positional_multi_errors():
    @validated
    def func(*items: Annotated[int, Check(lambda v: v > 0, "must be positive")]):
        return items

    try:
        func(1, -2, 3, -4)
        raise AssertionError("Should have raised")
    except ValidationError as e:
        errs = e.errors
        assert len(errs) == 2, f"Expected 2 errors, got {len(errs)}"
        assert errs[0].parameter_name == "items[1]"
        assert errs[0].value == -2
        assert errs[1].parameter_name == "items[3]"
        assert errs[1].value == -4


def test_check_in_var_keyword_multi_errors():
    @validated
    def func(
        **opts: Annotated[str, Check(lambda v: v.startswith("x"), "must start with x")],
    ):
        return opts

    try:
        func(a="xfoo", b="bar", c="xbaz", d="qux")
        raise AssertionError("Should have raised")
    except ValidationError as e:
        errs = e.errors
        assert len(errs) == 2, f"Expected 2 errors, got {len(errs)}"
        param_names = [err.parameter_name for err in errs]
        assert "opts['b']" in param_names
        assert "opts['d']" in param_names


# ── Run all ─────────────────────────────────────────────────────────────

print("\n=== Scenario 1: Check() with multi-parameter error collection ===")
run_test("Check multi-param (returns False)", test_check_multi_param_returning_false)
run_test("Check multi-param (predicate raises)", test_check_multi_param_raising_exception)
run_test("Check mixed with built-in validators", test_check_mixed_with_builtin_multi_param)

print("\n=== Scenario 2: Multiple validators in one Annotated[] ===")
run_test("Multi-validators: first fails", test_multi_validators_first_fails)
run_test("Multi-validators: second fails", test_multi_validators_second_fails)
run_test("Multi-validators: both pass", test_multi_validators_both_pass)
run_test(
    "Multi-validators: both fail (short-circuits to first)",
    test_multi_validators_both_fail_short_circuits,
)
run_test("Multi-validators: with Check()", test_multi_validators_with_check)
run_test(
    "Multi-validators: multi-param error collection",
    test_multi_validators_multi_param_error_collection,
)

print("\n=== Scenario 1+2 combined: Check() on *args / **kwargs ===")
run_test("Check in *args multi-errors", test_check_in_var_positional_multi_errors)
run_test("Check in **kwargs multi-errors", test_check_in_var_keyword_multi_errors)

print(f"\n{'=' * 60}")
print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
if failed:
    sys.exit(1)
