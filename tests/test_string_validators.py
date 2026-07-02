import pytest
from pydantic import ValidationError

from validated import (
    ContainsSubstring,
    EndsWith,
    IsLowerCase,
    IsUpperCase,
    StartsWith,
    Validated,
    validated,
)
from validated.validators.strings import MatchesPattern


def test_starts_with() -> None:
    @validated
    def process(text: Validated[str, StartsWith("hello")]):
        return text

    assert process("hello world") == "hello world"

    with pytest.raises(ValidationError) as excinfo:
        process("world hello")
    assert "must start with 'hello'" in excinfo.value.errors()[0]["msg"]


def test_ends_with() -> None:
    @validated
    def process(text: Validated[str, EndsWith("world")]):
        return text

    assert process("hello world") == "hello world"

    with pytest.raises(ValidationError) as excinfo:
        process("world hello")
    assert "must end with 'world'" in excinfo.value.errors()[0]["msg"]


def test_contains_substring() -> None:
    @validated
    def process(text: Validated[str, ContainsSubstring("foo")]):
        return text

    assert process("a foo b") == "a foo b"

    with pytest.raises(ValidationError) as excinfo:
        process("a bar b")
    assert "must contain substring 'foo'" in excinfo.value.errors()[0]["msg"]


def test_case_validators() -> None:
    @validated
    def process_lower(text: Validated[str, IsLowerCase()]):
        return text

    @validated
    def process_upper(text: Validated[str, IsUpperCase()]):
        return text

    assert process_lower("hello") == "hello"
    assert process_upper("HELLO") == "HELLO"

    with pytest.raises(ValidationError) as excinfo:
        process_lower("Hello")
    assert "must be lowercase" in excinfo.value.errors()[0]["msg"]

    with pytest.raises(ValidationError) as excinfo:
        process_upper("Hello")
    assert "must be uppercase" in excinfo.value.errors()[0]["msg"]


def test_strings_coverage() -> None:
    validators = [
        MatchesPattern("a"),
        StartsWith("a"),
        EndsWith("a"),
        ContainsSubstring("a"),
        IsLowerCase(),
        IsUpperCase(),
    ]
    for v in validators:
        assert not v.validate(123)
