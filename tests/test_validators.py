import numpy as np
import pytest
from pydantic import ValidationError

from validated import (
    Check,
    DType,
    GreaterThan,
    InRange,
    Length,
    LessThan,
    MatchesPattern,
    Shape,
    Validated,
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
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert errors[0]["input"] == "invalid"
    assert "valid integer" in errors[0]["msg"]


# 2. Test numeric validators
def test_numeric_validators():
    @validated
    def process_numbers(
        pos: Validated[int, GreaterThan(0)],
        neg: Validated[float, LessThan(0.0)],
        percent: Validated[float, InRange(0.0, 100.0)],
    ) -> float:
        return pos + neg + percent

    # Valid inputs
    assert process_numbers(5, -2.5, 50.0) == 52.5

    # GreaterThan violation
    with pytest.raises(ValidationError) as excinfo:
        process_numbers(0, -2.5, 50.0)
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert "must be greater than 0" in errors[0]["msg"]

    # LessThan violation
    with pytest.raises(ValidationError) as excinfo:
        process_numbers(5, 0.0, 50.0)
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (1,)
    assert "must be less than 0.0" in errors[0]["msg"]

    # InRange violation (too small)
    with pytest.raises(ValidationError) as excinfo:
        process_numbers(5, -2.5, -0.1)
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (2,)
    assert "must be in range [0.0, 100.0]" in errors[0]["msg"]

    # InRange violation (too large)
    with pytest.raises(ValidationError) as excinfo:
        process_numbers(5, -2.5, 100.1)
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (2,)
    assert "must be in range [0.0, 100.0]" in errors[0]["msg"]


# 3. Test string and collection validators
def test_string_and_collection_validators():
    @validated
    def process_strings(
        username: Validated[str, Length(min_len=3, max_len=10)],
        email: Validated[str, MatchesPattern(r"^[^@]+@[^@]+\.[^@]+$")],
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
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert "length must be between 3 and 10" in errors[0]["msg"]

    # Length violation (too long)
    with pytest.raises(ValidationError) as excinfo:
        process_strings("alice_long_name", "alice@example.com")
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)

    # Pattern violation
    with pytest.raises(ValidationError) as excinfo:
        process_strings("alice", "invalid-email")
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (1,)
    assert "must match pattern" in errors[0]["msg"]


# 4. Test custom validator Check
def test_custom_check():
    @validated
    def process_even(x: Validated[int, Check(lambda v: v % 2 == 0, "must be even")]):
        return x

    assert process_even(4) == 4

    with pytest.raises(ValidationError) as excinfo:
        process_even(5)
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert "must satisfy custom check: must be even" in errors[0]["msg"]


# 5. Test NumPy shape and dtype validators
def test_numpy_validators():
    @validated
    def process_array(
        arr: Validated[np.ndarray, Shape(None, 3), DType(np.float32)],
        vector: Validated[np.ndarray, Shape(5), DType("int64")],
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
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert "Input should be an instance of ndarray" in errors[0]["msg"]

    # Shape violation (wrong number of dimensions)
    with pytest.raises(ValidationError) as excinfo:
        process_array(np.ones(3, dtype=np.float32), v)
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert "does not match expected shape" in errors[0]["msg"]

    # Shape violation (wrong dimension size)
    with pytest.raises(ValidationError) as excinfo:
        process_array(np.ones((10, 4), dtype=np.float32), v)
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert "does not match expected shape" in errors[0]["msg"]

    # DType violation
    with pytest.raises(ValidationError) as excinfo:
        process_array(np.ones((10, 3), dtype=np.float64), v)
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert "does not match expected dtype" in errors[0]["msg"]

    # DType violation for vector
    with pytest.raises(ValidationError) as excinfo:
        process_array(a, np.zeros(5, dtype=np.int32))
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (1,)
    assert "does not match expected dtype" in errors[0]["msg"]


# 6. Test return value validators
def test_return_value_validators():
    @validated
    def get_positive(x: int) -> Validated[int, GreaterThan(0)]:
        return x

    assert get_positive(5) == 5

    with pytest.raises(ValidationError) as excinfo:
        get_positive(-5)
    errors = excinfo.value.errors()
    # Pydantic validate_call reports return validation errors under a specific loc or as a ValueError
    # It might just be an error with loc=() or similar depending on Pydantic version
    assert "must be greater than 0" in errors[0]["msg"]


# 7. Test var-positional and var-keyword arguments
def test_var_args_and_kwargs():
    @validated
    def process_many(
        *items: Validated[int, GreaterThan(0)],
        **options: Validated[float, InRange(0.0, 1.0)],
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
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (1,)
    assert errors[0]["input"] == -2

    # Keyword arg violation
    with pytest.raises(ValidationError) as excinfo:
        process_many(1, 2, alpha=1.5)
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == ("alpha",)
    assert errors[0]["input"] == 1.5


# 8. Test MatchesPattern uses fullmatch (not partial match)
def test_matches_pattern_fullmatch():
    @validated
    def process(code: Validated[str, MatchesPattern(r"\d{3}")]):
        return code

    # Exact match should pass
    assert process("123") == "123"

    # Partial match at start should FAIL
    with pytest.raises(ValidationError) as excinfo:
        process("123abc")
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert "must match pattern" in errors[0]["msg"]

    # Partial match at end should also FAIL
    with pytest.raises(ValidationError) as excinfo:
        process("abc123")
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)


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


# 11. Test Check exception chained context
def test_check_exception_chaining():
    """When a Check predicate raises an exception, Pydantic wraps it as a ValueError."""

    def buggy_predicate(value):
        return value.nonexistent_attribute

    @validated
    def process(x: Validated[int, Check(buggy_predicate, "buggy check")]):
        return x

    with pytest.raises(ValidationError) as excinfo:
        process(42)

    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert "AttributeError" in errors[0]["msg"]


def test_validator_reprs():
    import re

    import numpy as np

    from validated.validators.numpy import DType, Shape
    from validated.validators.paths import HasExtension, IsDirectory, IsFile, PathExists
    from validated.validators.sequences import Contains, Length, NonEmpty, Sorted, Unique
    from validated.validators.strings import (
        ContainsSubstring,
        EndsWith,
        IsLowerCase,
        IsUpperCase,
        MatchesPattern,
        StartsWith,
    )

    assert repr(MatchesPattern(r"\d+")) == "MatchesPattern(pattern='\\\\d+')"
    assert repr(StartsWith("foo")) == "StartsWith(prefix='foo')"
    assert repr(EndsWith("bar")) == "EndsWith(suffix='bar')"
    assert repr(ContainsSubstring("sub")) == "ContainsSubstring(substring='sub')"
    assert repr(IsLowerCase()) == "IsLowerCase()"
    assert repr(IsUpperCase()) == "IsUpperCase()"

    assert repr(Length(1, 10)) == "Length(min_len=1, max_len=10)"
    assert repr(NonEmpty()) == "NonEmpty()"
    assert repr(Contains("item")) == "Contains(item='item')"
    assert repr(Unique()) == "Unique()"
    assert repr(Sorted(reverse=True)) == "Sorted(reverse=True)"

    assert repr(PathExists()) == "PathExists()"
    assert repr(IsFile()) == "IsFile()"
    assert repr(IsDirectory()) == "IsDirectory()"
    assert repr(HasExtension(".txt")) == "HasExtension(extensions=('.txt',))"

    assert repr(Shape(1, 2)) == "Shape(dims=(1, 2))"
    assert repr(DType(np.float64)) == "DType(dtype=dtype('float64'))"


def test_missing_equality():
    from validated.validators.paths import HasExtension, IsDirectory, IsFile, PathExists
    from validated.validators.sequences import Contains, NonEmpty, Sorted, Unique
    from validated.validators.strings import ContainsSubstring, EndsWith, IsLowerCase, IsUpperCase, StartsWith

    assert StartsWith("foo") == StartsWith("foo")
    assert StartsWith("foo") != StartsWith("bar")

    assert EndsWith("bar") == EndsWith("bar")
    assert EndsWith("bar") != EndsWith("foo")

    assert ContainsSubstring("sub") == ContainsSubstring("sub")
    assert ContainsSubstring("sub") != ContainsSubstring("bus")

    assert IsLowerCase() == IsLowerCase()
    assert IsLowerCase() != IsUpperCase()

    assert IsUpperCase() == IsUpperCase()
    assert IsUpperCase() != IsLowerCase()

    assert NonEmpty() == NonEmpty()
    assert Contains("item") == Contains("item")
    assert Contains("item") != Contains("other")
    assert Unique() == Unique()
    assert Unique() != NonEmpty()

    assert Sorted() == Sorted()
    assert Sorted(reverse=True) == Sorted(reverse=True)
    assert Sorted() != Sorted(reverse=True)

    assert PathExists() == PathExists()
    assert IsFile() == IsFile()
    assert IsDirectory() == IsDirectory()
    assert HasExtension(".txt") == HasExtension(".txt")
    assert HasExtension(".txt") != HasExtension(".csv")


def test_string_compiled_regex():
    import re

    from validated.validators.strings import MatchesPattern

    compiled = re.compile(r"\d+")
    validator = MatchesPattern(compiled)
    assert validator.validate("123")
    assert not validator.validate("abc")


def test_sorted_empty_sequence():
    from validated.validators.sequences import Sorted

    assert Sorted().validate([])


def test_numpy_shape_list_and_str():
    import numpy as np

    from validated.validators.numpy import Shape

    # passing list
    validator = Shape([2, 3])
    assert validator.validate(np.zeros((2, 3)))

    # passing string digit
    validator2 = Shape("2", 3)
    assert validator2.validate(np.zeros((2, 3)))
    assert not validator2.validate(np.zeros((3, 3)))


def test_path_string_inputs():
    import os

    from validated.validators.paths import HasExtension, IsDirectory, IsFile, PathExists

    assert not PathExists().validate("/does/not/exist/ever")
    assert not IsFile().validate("/does/not/exist/ever.txt")
    assert not IsDirectory().validate("/does/not/exist/ever")
    assert HasExtension(".txt").validate("/some/path/file.txt")


def test_multi_validator_flatten_and_validate():
    from validated.validators.base import MultiValidator
    from validated.validators.comparisons import GreaterThan, LessThan

    v1 = GreaterThan(0)
    v2 = LessThan(10)
    m1 = MultiValidator([v1, v2])

    v3 = GreaterThan(2)
    m2 = MultiValidator([m1, v3])  # nested

    assert len(m2.validators) == 3
    assert m2.validate(5)
    assert not m2.validate(15)


def test_validator_check_error_propagation():
    from pydantic_core import core_schema

    from validated.validators.base import Validator
    from validated.validators.exceptions import ValidatorCheckError

    class FailingValidator(Validator):
        def validate(self, value):
            raise ValidatorCheckError("Custom error message", ValueError("inner"))

    schema = FailingValidator().__get_pydantic_core_schema__(str, lambda x: core_schema.str_schema())
    # we can test it implicitly using BaseModel
    from typing import Annotated

    from pydantic import BaseModel

    class TestModel(BaseModel):
        val: Annotated[str, FailingValidator()]

    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc:
        TestModel(val="test")
    assert "Custom error message" in str(exc.value)
