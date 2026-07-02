import pytest

from validated.validators.base import MultiValidator, Validated, Validator


def test_base_validator() -> None:
    class DummyValidator(Validator):
        pass

    v = DummyValidator()
    with pytest.raises(NotImplementedError):
        v.validate(5)

    assert v.error_message(5) == "Value 5 does not satisfy DummyValidator"


def test_multivalidator() -> None:
    mv = MultiValidator([])
    assert mv.error_message(5) == "multiple validators failed"


def test_validated_meta_branches() -> None:
    # If len(item) < 2, same as Annotated
    with pytest.raises(TypeError):
        _ = Validated[int]

    # If no validators are provided
    assert Validated[int, "metadata"] == __import__("typing").Annotated[int, "metadata"]
