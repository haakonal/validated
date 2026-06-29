from typing import Any


class ValidationError(ValueError):
    """Exception raised when one or more parameters or return value violates a validator."""

    parameter_name: str
    value: Any
    validator: Any
    message: str
    errors: list["ValidationError"]

    def __init__(
        self,
        parameter_name: Any = None,
        value: Any = None,
        validator: Any = None,
        message: Any = None,
        errors: list["ValidationError"] | None = None,
    ):
        self.errors = errors or []
        if self.errors:
            self.parameter_name = self.errors[0].parameter_name
            self.value = self.errors[0].value
            self.validator = self.errors[0].validator
            self.message = self.errors[0].message
        else:
            self.parameter_name = parameter_name
            self.value = value
            self.validator = validator
            self.message = message
            self.errors = [self]

        if len(self.errors) > 1:
            msg = "Validation failed for multiple parameters:\n" + "\n".join(
                f"- {err.parameter_name}: {err.message}" for err in self.errors
            )
            super().__init__(msg)
        else:
            super().__init__(
                f"Validation failed for parameter '{self.parameter_name}' with value {self.value!r}. "
                f"Validator violated: {self.message}"
            )
