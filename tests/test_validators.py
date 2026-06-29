from typing import Annotated

import numpy as np
import pytest

from validated import (
    Check,
    DType,
    GreaterThan,
    InRange,
    Length,
    LessThan,
    MatchesPattern,
    Shape,
    ValidationError,
    validated,
)


# 1. Test basic coercion and validation
def test_coercion_and_basic_validation():
    @validated
    def add_ints(a: int, b: int) -> int:
        return a + b

    # Valid values & coercion
    assert add_ints(5, 10) == 15
    assert add_ints("5", "10") == 15  # Coerced by Pydantic

    # Invalid values
    with pytest.raises(ValidationError) as excinfo:
        add_ints("invalid", 10)
    assert excinfo.value.parameter_name == "a"
    assert excinfo.value.value == "invalid"
    assert "type validation failed" in excinfo.value.message


# 2. Test numeric validators
def test_numeric_validators():
    @validated
    def process_numbers(
        pos: Annotated[int, GreaterThan(0)],
        neg: Annotated[float, LessThan(0.0)],
        percent: Annotated[float, InRange(0.0, 100.0)],
    ) -> float:
        return pos + neg + percent

    # Valid inputs
    assert process_numbers(5, -2.5, 50.0) == 52.5

    # GreaterThan violation
    with pytest.raises(ValidationError) as excinfo:
        process_numbers(0, -2.5, 50.0)
    assert excinfo.value.parameter_name == "pos"
    assert isinstance(excinfo.value.validator, GreaterThan)
    assert "must be greater than 0" in excinfo.value.message

    # LessThan violation
    with pytest.raises(ValidationError) as excinfo:
        process_numbers(5, 0.0, 50.0)
    assert excinfo.value.parameter_name == "neg"
    assert isinstance(excinfo.value.validator, LessThan)
    assert "must be less than 0.0" in excinfo.value.message

    # InRange violation (too small)
    with pytest.raises(ValidationError) as excinfo:
        process_numbers(5, -2.5, -0.1)
    assert excinfo.value.parameter_name == "percent"
    assert isinstance(excinfo.value.validator, InRange)
    assert "must be in range [0.0, 100.0]" in excinfo.value.message

    # InRange violation (too large)
    with pytest.raises(ValidationError) as excinfo:
        process_numbers(5, -2.5, 100.1)
    assert excinfo.value.parameter_name == "percent"
    assert isinstance(excinfo.value.validator, InRange)
    assert "must be in range [0.0, 100.0]" in excinfo.value.message


# 3. Test string and collection validators
def test_string_and_collection_validators():
    @validated
    def process_strings(
        username: Annotated[str, Length(min_len=3, max_len=10)],
        email: Annotated[str, MatchesPattern(r"^[^@]+@[^@]+\.[^@]+$")],
    ):
        return username, email

    # Valid inputs
    assert process_strings("alice", "alice@example.com") == (
        "alice",
        "alice@example.com",
    )

    # Length violation (too short)
    with pytest.raises(ValidationError) as excinfo:
        process_strings("ab", "alice@example.com")
    assert excinfo.value.parameter_name == "username"
    assert isinstance(excinfo.value.validator, Length)
    assert "length must be between 3 and 10" in excinfo.value.message

    # Length violation (too long)
    with pytest.raises(ValidationError) as excinfo:
        process_strings("alice_long_name", "alice@example.com")
    assert excinfo.value.parameter_name == "username"

    # Pattern violation
    with pytest.raises(ValidationError) as excinfo:
        process_strings("alice", "invalid-email")
    assert excinfo.value.parameter_name == "email"
    assert isinstance(excinfo.value.validator, MatchesPattern)
    assert "must match pattern" in excinfo.value.message


# 4. Test custom validator Check
def test_custom_check():
    @validated
    def process_even(x: Annotated[int, Check(lambda v: v % 2 == 0, "must be even")]):
        return x

    assert process_even(4) == 4

    with pytest.raises(ValidationError) as excinfo:
        process_even(5)
    assert excinfo.value.parameter_name == "x"
    assert isinstance(excinfo.value.validator, Check)
    assert "must satisfy custom check: must be even" in excinfo.value.message


# 5. Test NumPy shape and dtype validators
def test_numpy_validators():
    @validated
    def process_array(
        arr: Annotated[np.ndarray, Shape(None, 3), DType(np.float32)],
        vector: Annotated[np.ndarray, Shape(5), DType("int64")],
    ):
        return arr, vector

    # Valid inputs
    a = np.ones((10, 3), dtype=np.float32)
    v = np.zeros(5, dtype=np.int64)
    res_a, res_v = process_array(a, v)
    assert np.array_equal(res_a, a)
    assert np.array_equal(res_v, v)

    # Not an array
    with pytest.raises(ValidationError) as excinfo:
        process_array("not-an-array", v)  # type: ignore
    assert excinfo.value.parameter_name == "arr"
    assert "value is not a NumPy array" in excinfo.value.message

    # Shape violation (wrong number of dimensions)
    with pytest.raises(ValidationError) as excinfo:
        process_array(np.ones(3, dtype=np.float32), v)
    assert excinfo.value.parameter_name == "arr"
    assert "does not match expected shape" in excinfo.value.message

    # Shape violation (wrong dimension size)
    with pytest.raises(ValidationError) as excinfo:
        process_array(np.ones((10, 4), dtype=np.float32), v)
    assert excinfo.value.parameter_name == "arr"
    assert "does not match expected shape" in excinfo.value.message

    # DType violation
    with pytest.raises(ValidationError) as excinfo:
        process_array(np.ones((10, 3), dtype=np.float64), v)
    assert excinfo.value.parameter_name == "arr"
    assert "does not match expected dtype" in excinfo.value.message

    # DType violation for vector
    with pytest.raises(ValidationError) as excinfo:
        process_array(a, np.zeros(5, dtype=np.int32))
    assert excinfo.value.parameter_name == "vector"
    assert "does not match expected dtype" in excinfo.value.message


# 6. Test return value validators
def test_return_value_validators():
    @validated
    def get_positive(x: int) -> Annotated[int, GreaterThan(0)]:
        return x

    assert get_positive(5) == 5

    with pytest.raises(ValidationError) as excinfo:
        get_positive(-5)
    assert excinfo.value.parameter_name == "<return>"
    assert excinfo.value.value == -5
    assert isinstance(excinfo.value.validator, GreaterThan)
    assert "must be greater than 0" in excinfo.value.message


# 7. Test var-positional and var-keyword arguments
def test_var_args_and_kwargs():
    @validated
    def process_many(
        *items: Annotated[int, GreaterThan(0)],
        **options: Annotated[float, InRange(0.0, 1.0)],
    ):
        return items, options

    # Valid
    assert process_many(1, 2, 3, alpha=0.5, beta=0.8) == (
        (1, 2, 3),
        {"alpha": 0.5, "beta": 0.8},
    )

    # Coerced
    assert process_many("1", "2", alpha="0.5") == ((1, 2), {"alpha": 0.5})

    # Positional arg violation
    with pytest.raises(ValidationError) as excinfo:
        process_many(1, -2, 3)
    assert excinfo.value.parameter_name == "items[1]"
    assert excinfo.value.value == -2

    # Keyword arg violation
    with pytest.raises(ValidationError) as excinfo:
        process_many(1, 2, alpha=1.5)
    assert excinfo.value.parameter_name == "options['alpha']"
    assert excinfo.value.value == 1.5


# 8. Test MatchesPattern uses fullmatch (not partial match)
def test_matches_pattern_fullmatch():
    """Verify that MatchesPattern requires the ENTIRE string to match,
    not just the beginning (fullmatch semantics vs match semantics)."""

    @validated
    def process(code: Annotated[str, MatchesPattern(r"\d{3}")]):
        return code

    # Exact match should pass
    assert process("123") == "123"

    # Partial match at start should FAIL (would pass with re.match)
    with pytest.raises(ValidationError) as excinfo:
        process("123abc")
    assert excinfo.value.parameter_name == "code"
    assert "must match pattern" in excinfo.value.message

    # Partial match at end should also FAIL
    with pytest.raises(ValidationError) as excinfo:
        process("abc123")
    assert excinfo.value.parameter_name == "code"


# 9. Test __repr__ on all validator classes
def test_validator_repr():
    assert repr(GreaterThan(5)) == "GreaterThan(threshold=5)"
    assert repr(LessThan(2.0)) == "LessThan(threshold=2.0)"
    assert repr(InRange(0, 100)) == "InRange(min_val=0, max_val=100)"
    assert repr(Length(min_len=1, max_len=10)) == "Length(min_len=1, max_len=10)"
    assert repr(MatchesPattern(r"\d+")) == r"MatchesPattern(pattern='\\d+')"
    assert repr(Check(lambda x: x, "test")) == "Check(description='test')"
    assert repr(Shape(None, 3)) == "Shape(dims=(None, 3))"
    assert repr(DType("float64")) == "DType(dtype=dtype('float64'))"


# 10. Test __eq__ on all validator classes
def test_validator_equality():
    assert GreaterThan(5) == GreaterThan(5)
    assert GreaterThan(5) != GreaterThan(10)
    assert GreaterThan(5) != LessThan(5)

    assert LessThan(2.0) == LessThan(2.0)
    assert LessThan(2.0) != LessThan(3.0)

    assert InRange(0, 100) == InRange(0, 100)
    assert InRange(0, 100) != InRange(0, 50)

    assert Length(min_len=1, max_len=10) == Length(min_len=1, max_len=10)
    assert Length(min_len=1) != Length(max_len=1)

    assert MatchesPattern(r"\d+") == MatchesPattern(r"\d+")
    assert MatchesPattern(r"\d+") != MatchesPattern(r"\w+")

    # Check equality uses identity for predicates (lambdas are unique objects)
    def pred(x):
        return x > 0

    assert Check(pred, "pos") == Check(pred, "pos")
    assert Check(pred, "pos") != Check(pred, "different desc")
    assert Check(pred, "pos") != Check(lambda x: x > 0, "pos")  # different lambda object

    assert Shape(None, 3) == Shape(None, 3)
    assert Shape(3) != Shape(None, 3)

    assert DType("float64") == DType(np.float64)
    assert DType("float64") != DType("int32")


# 11. Test Check exception chaining via __cause__
def test_check_exception_chaining():
    """When a Check predicate raises an exception (e.g. AttributeError),
    the ValidationError should chain the original exception via __cause__."""

    def buggy_predicate(value):
        # This will raise AttributeError because int has no .nonexistent attribute
        return value.nonexistent_attribute

    @validated
    def process(x: Annotated[int, Check(buggy_predicate, "buggy check")]):
        return x

    with pytest.raises(ValidationError) as excinfo:
        process(42)

    # The ValidationError should exist
    assert excinfo.value.parameter_name == "x"
    assert excinfo.value.validator is not None
    assert isinstance(excinfo.value.validator, Check)

    # The original AttributeError should be chained as __cause__
    assert excinfo.value.__cause__ is not None
    assert isinstance(excinfo.value.__cause__, AttributeError)
