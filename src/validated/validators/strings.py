import re
from typing import Any

from validated.validators.base import Validator


class MatchesPattern(Validator):
    def __init__(self, pattern: str | re.Pattern[str]):
        if isinstance(pattern, str):
            self.regex = re.compile(pattern)
        else:
            self.regex = pattern

    def validate(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return bool(self.regex.fullmatch(value))

    def error_message(self, value: Any) -> str:
        return f"must match pattern {self.regex.pattern}"

    def __repr__(self) -> str:
        return f"MatchesPattern(pattern={self.regex.pattern!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MatchesPattern) and self.regex.pattern == other.regex.pattern


class StartsWith(Validator):
    def __init__(self, prefix: str):
        self.prefix = prefix

    def validate(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return value.startswith(self.prefix)

    def error_message(self, value: Any) -> str:
        return f"must start with {self.prefix!r}"

    def __repr__(self) -> str:
        return f"StartsWith(prefix={self.prefix!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, StartsWith) and self.prefix == other.prefix


class EndsWith(Validator):
    def __init__(self, suffix: str):
        self.suffix = suffix

    def validate(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return value.endswith(self.suffix)

    def error_message(self, value: Any) -> str:
        return f"must end with {self.suffix!r}"

    def __repr__(self) -> str:
        return f"EndsWith(suffix={self.suffix!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EndsWith) and self.suffix == other.suffix


class ContainsSubstring(Validator):
    def __init__(self, substring: str):
        self.substring = substring

    def validate(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return self.substring in value

    def error_message(self, value: Any) -> str:
        return f"must contain substring {self.substring!r}"

    def __repr__(self) -> str:
        return f"ContainsSubstring(substring={self.substring!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ContainsSubstring) and self.substring == other.substring


class IsLowerCase(Validator):
    def validate(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return value.islower()

    def error_message(self, value: Any) -> str:
        return "must be lowercase"

    def __repr__(self) -> str:
        return "IsLowerCase()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, IsLowerCase)


class IsUpperCase(Validator):
    def validate(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return value.isupper()

    def error_message(self, value: Any) -> str:
        return "must be uppercase"

    def __repr__(self) -> str:
        return "IsUpperCase()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, IsUpperCase)
