import pytest

from validated.loaders import dump_validator, load_validator
from validated.validators import (
    DType,
    HasExtension,
    InRange,
    Length,
    LessThan,
    MatchesPattern,
    NonEmpty,
    Shape,
    StartsWith,
)


def test_load_and_dump_simple_validators():
    # LessThan
    v = load_validator({"type": "LessThan", "parameters": {"threshold": 5.0}})
    assert isinstance(v, LessThan)
    assert v.threshold == 5.0
    dumped = dump_validator(v)
    assert dumped == {"type": "LessThan", "parameters": {"threshold": 5.0}}

    # InRange
    v2 = load_validator({"type": "InRange", "parameters": {"min_val": 1, "max_val": 10}})
    assert isinstance(v2, InRange)
    assert v2.min_val == 1
    assert v2.max_val == 10
    dumped2 = dump_validator(v2)
    assert dumped2 == {"type": "InRange", "parameters": {"min_val": 1, "max_val": 10}}


def test_load_and_dump_no_param_validators():
    v = load_validator({"type": "NonEmpty"})
    assert isinstance(v, NonEmpty)
    dumped = dump_validator(v)
    assert dumped == {"type": "NonEmpty", "parameters": {}}


def test_load_and_dump_string_validators():
    v = load_validator({"type": "StartsWith", "parameters": {"prefix": "abc"}})
    assert isinstance(v, StartsWith)
    assert v.prefix == "abc"
    dumped = dump_validator(v)
    assert dumped == {"type": "StartsWith", "parameters": {"prefix": "abc"}}

    v2 = load_validator({"type": "MatchesPattern", "parameters": {"pattern": "^abc"}})
    assert isinstance(v2, MatchesPattern)
    dumped2 = dump_validator(v2)
    assert dumped2 == {"type": "MatchesPattern", "parameters": {"pattern": "^abc"}}


def test_load_and_dump_sequence_validators():
    v = load_validator({"type": "Length", "parameters": {"min_len": 2}})
    assert isinstance(v, Length)
    assert v.min_len == 2
    assert v.max_len is None
    dumped = dump_validator(v)
    assert dumped == {"type": "Length", "parameters": {"min_len": 2}}


def test_load_and_dump_numpy_validators():
    v = load_validator({"type": "Shape", "parameters": {"dims": [None, 3]}})
    assert isinstance(v, Shape)
    assert v.dims == (None, 3)
    dumped = dump_validator(v)
    # Shape converts dims to tuple, so it might dump as tuple. JSON serializer will handle tuple to list.
    assert dumped["type"] == "Shape"
    assert list(dumped["parameters"]["dims"]) == [None, 3]

    v2 = load_validator({"type": "DType", "parameters": {"dtype": "float64"}})
    assert isinstance(v2, DType)
    assert str(v2.expected_dtype) == "float64"
    dumped2 = dump_validator(v2)
    assert dumped2["type"] == "DType"
    assert dumped2["parameters"]["dtype"] == "float64"


def test_load_and_dump_path_validators():
    v = load_validator({"type": "HasExtension", "parameters": {"extensions": [".json", ".txt"]}})
    assert isinstance(v, HasExtension)
    assert set(v.extensions) == {".json", ".txt"}
    dumped = dump_validator(v)
    assert dumped["type"] == "HasExtension"
    assert set(dumped["parameters"]["extensions"]) == {".json", ".txt"}


def test_invalid_load():
    with pytest.raises(ValueError, match="Missing 'type'"):
        load_validator({"parameters": {}})

    with pytest.raises(ValueError, match="Unknown validator type: UnknownType"):
        load_validator({"type": "UnknownType"})


class CustomValidator:
    pass


def test_invalid_dump():
    v = CustomValidator()
    with pytest.raises(ValueError, match="Cannot dump unregistered validator type"):
        dump_validator(v)  # type: ignore
