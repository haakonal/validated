from typing import Any

class ConstraintValidationError(ValueError):
    """Exception raised when a parameter or return value violates a constraint."""

    def __init__(self, parameter_name: str, value: Any, constraint: Any, message: str):
        self.parameter_name = parameter_name
        self.value = value
        self.constraint = constraint
        self.message = message
        super().__init__(
            f"Validation failed for parameter '{parameter_name}' with value {value!r}. "
            f"Constraint violated: {message}"
        )
