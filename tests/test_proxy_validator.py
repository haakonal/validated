import pytest
from pydantic import BaseModel, ValidationError

from validated import Validated, validated
from validated.validators import LessThan, Validator
from validated.validators.proxy import ProxyValidator, ValidatorProvider


class MockProvider(ValidatorProvider):
    def __init__(self):
        self.rules = {}

    def set_rule(self, context_name: str, parameter_name: str, validator: Validator):
        self.rules[(context_name, parameter_name)] = validator

    def get_validator(self, context_name: str, parameter_name: str) -> Validator:
        key = (context_name, parameter_name)
        if key not in self.rules:
            raise ValueError(f"No rule found for {context_name}:{parameter_name}")
        return self.rules[key]


def test_proxy_validator_dynamic_reloading():
    provider = MockProvider()

    # Initialize with a LessThan(10) rule
    provider.set_rule("test_ctx", "param1", LessThan(10))

    proxy = ProxyValidator("test_ctx", "param1", provider)

    @validated
    def my_func(a: Validated[int, proxy]):
        return a

    # Should pass
    assert my_func(5) == 5

    # Should fail
    with pytest.raises(ValidationError, match="must be less than 10"):
        my_func(15)

    # Now simulate a hot-reload by changing the database/provider rule
    provider.set_rule("test_ctx", "param1", LessThan(20))

    # The exact same function should now pass for 15!
    assert my_func(15) == 15

    # But fail for 25
    with pytest.raises(ValidationError, match="must be less than 20"):
        my_func(25)


def test_proxy_validator_pydantic_model():
    provider = MockProvider()
    provider.set_rule("model_ctx", "field", LessThan(5))

    proxy = ProxyValidator("model_ctx", "field", provider)

    class MyModel(BaseModel):
        val: Validated[int, proxy]

    # Should pass
    model = MyModel(val=3)
    assert model.val == 3

    # Should fail
    with pytest.raises(ValidationError, match="must be less than 5"):
        MyModel(val=8)

    # Hot reload
    provider.set_rule("model_ctx", "field", LessThan(10))

    # Should now pass
    model2 = MyModel(val=8)
    assert model2.val == 8
