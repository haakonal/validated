from abc import ABC, abstractmethod
from typing import Any

from validated.validators.base import Validator


class ValidatorProvider(ABC):
    """Abstract base class for providing validators dynamically."""

    @abstractmethod
    def get_validator(self, context_name: str, parameter_name: str) -> Validator:
        """Fetch the active Validator for a given context and parameter.

        Args:
            context_name: The overarching context (e.g., 'slew_task', 'tenant_a_rules')
            parameter_name: The specific parameter being validated (e.g., 'max_speed')

        Returns:
            The Validator instance to apply.

        Raises:
            ValueError: If no rule is found for the given context and parameter.
        """
        pass


class ProxyValidator(Validator):
    """A proxy validator that fetches its target dynamically at execution time.

    This is useful for hot-reloading rules without restarting the application,
    as Pydantic evaluates annotations exactly once at import-time. By wrapping
    dynamic lookups in a ProxyValidator, Pydantic's core schema remains static
    while the validation logic changes dynamically.
    """

    def __init__(self, context_name: str, parameter_name: str, provider: ValidatorProvider):
        self.context_name = context_name
        self.parameter_name = parameter_name
        self.provider = provider

    def _get_active_constraint(self) -> Validator:
        return self.provider.get_validator(self.context_name, self.parameter_name)

    def validate(self, value: Any) -> bool:
        return self._get_active_constraint().validate(value)

    def error_message(self, value: Any) -> str:
        return self._get_active_constraint().error_message(value)

    # We do not override __get_pydantic_core_schema__. The base class implementation
    # works perfectly: it generates an `_after_validate` function which calls `self.validate()`.
    # Since `self.validate()` delegates dynamically on each call, it correctly
    # hooks into Pydantic while fetching the latest constraint!
