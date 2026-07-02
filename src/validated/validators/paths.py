from pathlib import Path
from typing import Any

from validated.validators.base import Validator


class PathExists(Validator):
    def validate(self, value: Any) -> bool:
        if isinstance(value, str):
            value = Path(value)
        if not isinstance(value, Path):
            return False
        return value.exists()

    def error_message(self, value: Any) -> str:
        return f"path does not exist: {value}"

    def __repr__(self) -> str:
        return "PathExists()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PathExists)


class IsFile(Validator):
    def validate(self, value: Any) -> bool:
        if isinstance(value, str):
            value = Path(value)
        if not isinstance(value, Path):
            return False
        return value.is_file()

    def error_message(self, value: Any) -> str:
        return f"path is not a file: {value}"

    def __repr__(self) -> str:
        return "IsFile()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, IsFile)


class IsDirectory(Validator):
    def validate(self, value: Any) -> bool:
        if isinstance(value, str):
            value = Path(value)
        if not isinstance(value, Path):
            return False
        return value.is_dir()

    def error_message(self, value: Any) -> str:
        return f"path is not a directory: {value}"

    def __repr__(self) -> str:
        return "IsDirectory()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, IsDirectory)


class HasExtension(Validator):
    def __init__(self, *extensions: str):
        # Normalize extensions (ensure they start with a dot)
        self.extensions = tuple(ext if ext.startswith(".") else f".{ext}" for ext in extensions)

    def validate(self, value: Any) -> bool:
        if isinstance(value, str):
            value = Path(value)
        if not isinstance(value, Path):
            return False
        return value.suffix in self.extensions

    def error_message(self, value: Any) -> str:
        return f"file extension {getattr(value, 'suffix', '')} not in {self.extensions}"

    def __repr__(self) -> str:
        return f"HasExtension(extensions={self.extensions!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, HasExtension) and self.extensions == other.extensions
