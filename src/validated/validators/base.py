from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from validated.validators.exceptions import ValidatorCheckError


class Validator:
    """Base class for all validators."""

    def validate(self, value: Any) -> bool:
        raise NotImplementedError

    def error_message(self, value: Any) -> str:
        return f"Value {value!r} does not satisfy {self.__class__.__name__}"

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        """Hook into Pydantic v2 so this validator works as Annotated metadata on BaseModel fields."""
        schema = handler(source_type)

        def _after_validate(value: Any) -> Any:
            try:
                if not self.validate(value):
                    raise ValueError(self.error_message(value))
            except ValidatorCheckError as exc:
                raise ValueError(str(exc)) from exc
            return value

        return core_schema.no_info_after_validator_function(_after_validate, schema)


class MultiValidator(Validator):
    """Internal validator used to group multiple validators for Pydantic core schema."""

    def __init__(self, validators: list[Validator]):
        flat_validators = []
        for v in validators:
            if isinstance(v, MultiValidator):
                flat_validators.extend(v.validators)
            else:
                flat_validators.append(v)
        self.validators = flat_validators

    def validate(self, value: Any) -> bool:
        return all(v.validate(value) for v in self.validators)

    def error_message(self, value: Any) -> str:
        return "multiple validators failed"

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        schema = handler(source_type)

        def _after_validate(value: Any) -> Any:
            errors = []
            for validator in self.validators:
                try:
                    passed = validator.validate(value)
                    if not passed:
                        errors.append(validator.error_message(value))
                except ValidatorCheckError as exc:
                    errors.append(str(exc))

            if errors:
                raise ValueError("\n".join(errors))
            return value

        return core_schema.no_info_after_validator_function(_after_validate, schema)


class _ValidatedMeta(type):
    """Metaclass to support Validated[BaseType, Validator1, Validator2] syntax."""

    def __getitem__(cls, item: Any) -> Any:
        from typing import Annotated

        if not isinstance(item, tuple) or len(item) < 2:
            return Annotated[item]

        base_type = item[0]
        validators = [v for v in item[1:] if isinstance(v, Validator)]
        other_metadata = [v for v in item[1:] if not isinstance(v, Validator)]

        if not validators:
            return Annotated[item]

        combined = MultiValidator(validators)
        return Annotated[(base_type, combined, *other_metadata)]


if TYPE_CHECKING:
    from typing import Annotated as Validated
else:

    class Validated(metaclass=_ValidatedMeta):
        """
        A type annotation for validated constraints.
        Replaces typing.Annotated to automatically collect multiple validation errors.
        """

        pass


class ValidatorBaseModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)
