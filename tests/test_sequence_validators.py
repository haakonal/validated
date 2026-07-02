import pytest
from pydantic import ValidationError

from validated import (
    Contains,
    NonEmpty,
    Sorted,
    Unique,
    Validated,
    validated,
)


def test_non_empty():
    @validated
    def process(items: Validated[list[int], NonEmpty()]):
        return items

    assert process([1]) == [1]

    with pytest.raises(ValidationError) as excinfo:
        process([])
    assert "must not be empty" in excinfo.value.errors()[0]["msg"]


def test_contains():
    @validated
    def process(items: Validated[list[int], Contains(5)]):
        return items

    assert process([1, 5, 10]) == [1, 5, 10]

    with pytest.raises(ValidationError) as excinfo:
        process([1, 2, 3])
    assert "must contain 5" in excinfo.value.errors()[0]["msg"]


def test_unique():
    @validated
    def process(items: Validated[list[int], Unique()]):
        return items

    assert process([1, 2, 3]) == [1, 2, 3]

    with pytest.raises(ValidationError) as excinfo:
        process([1, 2, 2])
    assert "all elements must be unique" in excinfo.value.errors()[0]["msg"]


def test_sorted():
    @validated
    def process_asc(items: Validated[list[int], Sorted()]):
        return items

    @validated
    def process_desc(items: Validated[list[int], Sorted(reverse=True)]):
        return items

    assert process_asc([1, 2, 3]) == [1, 2, 3]
    assert process_desc([3, 2, 1]) == [3, 2, 1]

    with pytest.raises(ValidationError) as excinfo:
        process_asc([1, 3, 2])
    assert "elements must be in ascending order" in excinfo.value.errors()[0]["msg"]

    with pytest.raises(ValidationError) as excinfo:
        process_desc([1, 2, 3])
    assert "elements must be in descending order" in excinfo.value.errors()[0]["msg"]


def test_sequences_coverage():
    # Length TypeError
    from validated.validators.sequences import Length

    length_val = Length(min_len=1, max_len=5)
    assert not length_val.validate(123)

    # Length error messages
    assert "at least 5" in Length(min_len=5).error_message(1)
    assert "at most 2" in Length(max_len=2).error_message(1)
    assert "invalid length" in Length().error_message(1)

    # NonEmpty error message
    ne = NonEmpty()
    assert ne.error_message(1) == "must not be empty"

    # Contains TypeError
    c = Contains(5)
    assert not c.validate(123)

    # Sorted TypeError
    s = Sorted()
    assert not s.validate(123)

    # Unique fallback for unhashable types
    u = Unique()
    assert u.validate([[1], [2], [3]]) is True
    assert u.validate([[1], [2], [1]]) is False
    assert u.validate(123) is False
