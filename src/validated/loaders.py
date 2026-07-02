from typing import Any

from validated.validators.base import Validator
from validated.validators.comparisons import GreaterThan, InRange, LessThan
from validated.validators.numpy import DType, Shape
from validated.validators.paths import HasExtension, IsDirectory, IsFile, PathExists
from validated.validators.sequences import Contains, Length, NonEmpty, Sorted, Unique
from validated.validators.strings import (
    ContainsSubstring,
    EndsWith,
    IsLowerCase,
    IsUpperCase,
    MatchesPattern,
    StartsWith,
)

VALIDATOR_REGISTRY: dict[str, type[Validator]] = {
    "GreaterThan": GreaterThan,
    "InRange": InRange,
    "LessThan": LessThan,
    "DType": DType,
    "Shape": Shape,
    "HasExtension": HasExtension,
    "IsDirectory": IsDirectory,
    "IsFile": IsFile,
    "PathExists": PathExists,
    "Contains": Contains,
    "Length": Length,
    "NonEmpty": NonEmpty,
    "Sorted": Sorted,
    "Unique": Unique,
    "ContainsSubstring": ContainsSubstring,
    "EndsWith": EndsWith,
    "IsLowerCase": IsLowerCase,
    "IsUpperCase": IsUpperCase,
    "MatchesPattern": MatchesPattern,
    "StartsWith": StartsWith,
}


def load_validator(config: dict[str, Any]) -> Validator:
    """Instantiate a Validator from a dictionary payload.

    Expected format:
    {
        "type": "LessThan",
        "parameters": {"threshold": 2.0}
    }
    """
    if "type" not in config:
        raise ValueError("Missing 'type' key in validator config.")

    val_type = config["type"]
    parameters = config.get("parameters", {})

    cls = VALIDATOR_REGISTRY.get(val_type)
    if not cls:
        raise ValueError(f"Unknown validator type: {val_type}")

    if val_type == "HasExtension":
        return cls(*parameters.get("extensions", []))
    if val_type == "Shape":
        return cls(*parameters.get("dims", []))

    return cls(**parameters)


def dump_validator(validator: Validator) -> dict[str, Any]:
    """Serialize a standard Validator back to a dictionary."""
    val_type = validator.__class__.__name__

    if val_type not in VALIDATOR_REGISTRY:
        raise ValueError(f"Cannot dump unregistered validator type: {val_type}")

    # Standard extraction logic based on the class properties.
    # Note: For some validators, we need to handle specific attribute names that differ from __init__.
    parameters = {}
    if type(validator) in (GreaterThan, LessThan):
        parameters["threshold"] = validator.threshold
    elif type(validator) is InRange:
        parameters["min_val"] = validator.min_val
        parameters["max_val"] = validator.max_val
    elif type(validator) is Length:
        if validator.min_len is not None:
            parameters["min_len"] = validator.min_len
        if validator.max_len is not None:
            parameters["max_len"] = validator.max_len
    elif type(validator) is MatchesPattern:
        # We need to extract the pattern string from the compiled regex
        parameters["pattern"] = validator.regex.pattern
    elif type(validator) in (StartsWith, EndsWith, ContainsSubstring):
        # Usually prefix, suffix, substring
        if hasattr(validator, "prefix"):
            parameters["prefix"] = validator.prefix
        if hasattr(validator, "suffix"):
            parameters["suffix"] = validator.suffix
        if hasattr(validator, "substring"):
            parameters["substring"] = validator.substring
    elif type(validator) is Contains:
        parameters["item"] = validator.item
    elif type(validator) is HasExtension:
        parameters["extensions"] = list(validator.extensions)
    elif type(validator) is DType:
        parameters["dtype"] = str(validator.expected_dtype)
    elif type(validator) is Shape:
        parameters["dims"] = validator.dims
    elif type(validator) is Sorted:
        parameters["reverse"] = validator.reverse
    # Validators with no parameters like NonEmpty, Unique, IsFile, etc. will just return empty dicts for parameters

    return {
        "type": val_type,
        "parameters": parameters,
    }
