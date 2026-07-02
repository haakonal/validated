from pathlib import Path

import pytest
from pydantic import ValidationError

from validated import (
    HasExtension,
    IsDirectory,
    IsFile,
    PathExists,
    Validated,
    validated,
)


@pytest.fixture
def temp_fs(tmp_path: Path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello")
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    return {
        "file": test_file,
        "dir": test_dir,
        "missing": tmp_path / "missing.txt",
    }


def test_path_exists(temp_fs):
    @validated
    def check_exists(path: Validated[Path, PathExists()]):
        return path

    # Should pass for both file and dir
    assert check_exists(temp_fs["file"]) == temp_fs["file"]
    assert check_exists(temp_fs["dir"]) == temp_fs["dir"]

    with pytest.raises(ValidationError) as excinfo:
        check_exists(temp_fs["missing"])
    errors = excinfo.value.errors()
    assert errors[0]["loc"] == (0,)
    assert "path does not exist" in errors[0]["msg"]


def test_is_file(temp_fs):
    @validated
    def check_file(path: Validated[Path, IsFile()]):
        return path

    assert check_file(temp_fs["file"]) == temp_fs["file"]

    # Fails on directory
    with pytest.raises(ValidationError) as excinfo:
        check_file(temp_fs["dir"])
    assert "path is not a file" in excinfo.value.errors()[0]["msg"]

    # Fails on missing
    with pytest.raises(ValidationError):
        check_file(temp_fs["missing"])


def test_is_directory(temp_fs):
    @validated
    def check_dir(path: Validated[Path, IsDirectory()]):
        return path

    assert check_dir(temp_fs["dir"]) == temp_fs["dir"]

    # Fails on file
    with pytest.raises(ValidationError) as excinfo:
        check_dir(temp_fs["file"])
    assert "path is not a directory" in excinfo.value.errors()[0]["msg"]

    # Fails on missing
    with pytest.raises(ValidationError):
        check_dir(temp_fs["missing"])


def test_has_extension():
    @validated
    def check_ext(path: Validated[Path, HasExtension(".csv", "txt")]):
        return path

    # Should pass regardless of existence
    assert check_ext("data.csv") == Path("data.csv")
    assert check_ext(Path("file.txt")) == Path("file.txt")

    with pytest.raises(ValidationError) as excinfo:
        check_ext("image.png")
    errors = excinfo.value.errors()
    assert ".png not in" in errors[0]["msg"]


def test_paths_coverage():
    validators = [PathExists(), IsFile(), IsDirectory(), HasExtension(".txt")]
    for v in validators:
        assert not v.validate(123)

    h = HasExtension(".txt")
    assert "not in" in h.error_message(123)
