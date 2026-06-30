"""Tests for Pydantic ValidatorBaseModel integration.

Verifies that our Validator classes work natively as Annotated metadata
on ValidatorBaseModel fields via __get_pydantic_core_schema__.
"""

from typing import Annotated

import pytest
from pydantic import ValidationError as PydanticValidationError

from validated import (
    Check,
    GreaterThan,
    InRange,
    Length,
    LessThan,
    MatchesPattern,
    Validated,
    ValidatorBaseModel,
)

# --- 1. Basic numeric validators on a ValidatorBaseModel ---


class NumericConfig(ValidatorBaseModel):
    positive: Annotated[int, GreaterThan(0)]
    negative: Annotated[float, LessThan(0.0)]
    percent: Annotated[float, InRange(0.0, 100.0)]


def test_numeric_validators_pass():
    config = NumericConfig(positive=5, negative=-2.5, percent=50.0)
    assert config.positive == 5
    assert config.negative == -2.5
    assert config.percent == 50.0


def test_greater_than_violation():
    with pytest.raises(PydanticValidationError) as excinfo:
        NumericConfig(positive=0, negative=-1.0, percent=50.0)
    assert "must be greater than 0" in str(excinfo.value)


def test_less_than_violation():
    with pytest.raises(PydanticValidationError) as excinfo:
        NumericConfig(positive=1, negative=5.0, percent=50.0)
    assert "must be less than 0.0" in str(excinfo.value)


def test_in_range_violation_too_low():
    with pytest.raises(PydanticValidationError) as excinfo:
        NumericConfig(positive=1, negative=-1.0, percent=-0.1)
    assert "must be in range [0.0, 100.0]" in str(excinfo.value)


def test_in_range_violation_too_high():
    with pytest.raises(PydanticValidationError) as excinfo:
        NumericConfig(positive=1, negative=-1.0, percent=100.1)
    assert "must be in range [0.0, 100.0]" in str(excinfo.value)


def test_validate_assignment():
    config = NumericConfig(positive=5, negative=-2.5, percent=50.0)

    # Valid assignment should work
    config.positive = 10
    assert config.positive == 10

    # Invalid assignment should raise PydanticValidationError
    with pytest.raises(PydanticValidationError) as excinfo:
        config.positive = -5
    assert "must be greater than 0" in str(excinfo.value)

    with pytest.raises(PydanticValidationError) as excinfo:
        config.percent = 150.0
    assert "must be in range [0.0, 100.0]" in str(excinfo.value)


# --- 2. String validators on a ValidatorBaseModel ---


class StringConfig(ValidatorBaseModel):
    username: Annotated[str, Length(min_len=3, max_len=10)]
    subsystem_id: Annotated[str, MatchesPattern(r"^(ACS|PWR|COM)-\d{3}$")]


def test_string_validators_pass():
    config = StringConfig(username="alice", subsystem_id="ACS-101")
    assert config.username == "alice"
    assert config.subsystem_id == "ACS-101"


def test_length_violation_too_short():
    with pytest.raises(PydanticValidationError) as excinfo:
        StringConfig(username="ab", subsystem_id="ACS-101")
    assert "length must be between 3 and 10" in str(excinfo.value)


def test_length_violation_too_long():
    with pytest.raises(PydanticValidationError) as excinfo:
        StringConfig(username="alice_too_long", subsystem_id="ACS-101")
    assert "length must be between 3 and 10" in str(excinfo.value)


def test_pattern_violation():
    with pytest.raises(PydanticValidationError) as excinfo:
        StringConfig(username="alice", subsystem_id="INVALID")
    assert "must match pattern" in str(excinfo.value)


# --- 3. Custom Check validator on a ValidatorBaseModel ---


class EvenConfig(ValidatorBaseModel):
    value: Annotated[int, Check(lambda v: v % 2 == 0, "must be even")]


def test_check_validator_pass():
    config = EvenConfig(value=4)
    assert config.value == 4


def test_check_validator_violation():
    with pytest.raises(PydanticValidationError) as excinfo:
        EvenConfig(value=5)
    assert "must satisfy custom check: must be even" in str(excinfo.value)


# --- 4. Multiple validators on a single field ---


class MultiValidatorConfig(ValidatorBaseModel):
    score: Annotated[float, GreaterThan(0.0), LessThan(100.0)]


def test_multi_validator_pass():
    config = MultiValidatorConfig(score=50.0)
    assert config.score == 50.0


def test_multi_validator_first_fails():
    with pytest.raises(PydanticValidationError) as excinfo:
        MultiValidatorConfig(score=-1.0)
    assert "must be greater than 0.0" in str(excinfo.value)


def test_multi_validator_second_fails():
    with pytest.raises(PydanticValidationError) as excinfo:
        MultiValidatorConfig(score=100.0)
    assert "must be less than 100.0" in str(excinfo.value)


class MultiBothFailConfig(ValidatorBaseModel):
    score: Validated[float, GreaterThan(100.0), LessThan(0.0)]


def test_multi_validator_both_fail():
    with pytest.raises(PydanticValidationError) as excinfo:
        MultiBothFailConfig(score=50.0)
    err_str = str(excinfo.value)
    assert "must be greater than 100.0" in err_str
    assert "must be less than 0.0" in err_str


# --- 5. Using the Validated alias ---


class AliasConfig(ValidatorBaseModel):
    speed: Validated[float, LessThan(2.0)]
    charge: Validated[float, InRange(50.0, 100.0)]


def test_validated_alias_pass():
    config = AliasConfig(speed=1.5, charge=80.0)
    assert config.speed == 1.5
    assert config.charge == 80.0


def test_validated_alias_violation():
    with pytest.raises(PydanticValidationError) as excinfo:
        AliasConfig(speed=3.0, charge=80.0)
    assert "must be less than 2.0" in str(excinfo.value)


# --- 6. Pydantic type coercion still works ---


class CoercionConfig(ValidatorBaseModel):
    count: Annotated[int, GreaterThan(0)]


def test_pydantic_coercion_with_validators():
    """String '5' should be coerced to int 5, then GreaterThan(0) should pass."""
    config = CoercionConfig(count="5")  # type: ignore
    assert config.count == 5
    assert isinstance(config.count, int)


def test_pydantic_coercion_then_validation_fails():
    """String '0' should be coerced to int 0, then GreaterThan(0) should fail."""
    with pytest.raises(PydanticValidationError) as excinfo:
        CoercionConfig(count="0")  # type: ignore
    assert "must be greater than 0" in str(excinfo.value)


class CheckErrorConfig(ValidatorBaseModel):
    value: Validated[int, GreaterThan(0), Check(lambda v: 1 / 0, "division by zero")]


def test_multi_validator_check_error():
    with pytest.raises(PydanticValidationError) as excinfo:
        CheckErrorConfig(value=5)
    err_str = str(excinfo.value)
    assert "must satisfy custom check: division by zero" in err_str
