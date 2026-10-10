"""Tests de ``validate_path`` y ``validate_optional_path`` (_core/validation/paths.py, v1.1.0)."""

from __future__ import annotations

import os

from pathlib import Path, PurePosixPath

import pytest

from util_bbdd._core.validation import validate_optional_path, validate_path


class _FsPath:
    """``os.PathLike[str]`` que no es ``pathlib.Path``."""

    def __init__(self, raw: str) -> None:
        self.raw = raw

    def __fspath__(self) -> str:
        return self.raw


class _BytesPath:
    def __fspath__(self) -> bytes:
        return b"salida"


class TestValidatePath:
    def test_path_is_returned_as_is(self, tmp_path: Path) -> None:
        assert validate_path(tmp_path, "output_dir") is tmp_path

    def test_str_becomes_path_without_resolving(self) -> None:
        result = validate_path("salida/audit.csv", "audit_csv_path")

        assert result == Path("salida/audit.csv")
        assert not result.is_absolute()

    def test_pathlike_str_becomes_path(self) -> None:
        assert validate_path(_FsPath("salida"), "output_dir") == Path("salida")

    def test_pure_path_is_accepted(self) -> None:
        assert validate_path(PurePosixPath("a/b"), "output_dir") == Path("a/b")

    @pytest.mark.parametrize("value", [123, 1.5, b"salida", _BytesPath(), None, ["a"]])
    def test_other_types_raise_value_error_naming_the_parameter(self, value: object) -> None:
        with pytest.raises(ValueError, match=r"output_dir debe ser una ruta \(str o Path\)"):
            validate_path(value, "output_dir")

    def test_home_and_variables_are_not_expanded(self) -> None:
        raw = os.path.join("~", "$HOME", "x.csv")

        assert str(validate_path(raw, "audit_csv_path")) == str(Path(raw))


class TestValidateOptionalPath:
    def test_none_is_returned(self) -> None:
        assert validate_optional_path(None, "bulk_audit_path") is None

    def test_str_becomes_path(self) -> None:
        assert validate_optional_path("b.csv", "bulk_audit_path") == Path("b.csv")

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(ValueError, match="bulk_audit_path"):
            validate_optional_path(7, "bulk_audit_path")
