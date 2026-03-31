"""Tests focalizados para la carga separada de configuracion de drivers."""

from __future__ import annotations

import json

from pathlib import Path

import pytest

from util_bbdd._drivers._config_loader import load_database_type_config
from util_bbdd._drivers.validator import DatabaseTypeValidator


def _write_config(config_file: Path, *, db_name: str = "MariaDB") -> None:
    config_file.write_text(
        json.dumps(
            {
                "metadata": {"supported_db_types": ["mariadb"]},
                "database_types": {
                    "mariadb": {
                        "name": db_name,
                        "description": "Motor de prueba",
                        "default_port": 3306,
                        "supported_features": ["async"],
                        "driver_info": {"sync": "mariadb"},
                        "connection_params": {
                            "required": ["host", "database"],
                            "optional": [{"name": "charset"}],
                        },
                    }
                },
                "examples": {"mariadb": {"database": "demo"}},
                "error_messages": {"unknown": "Error {code}"},
                "compatibility": {"legacy": True},
            }
        ),
        encoding="utf-8",
    )


def test_load_database_type_config_reads_json_file(tmp_path: Path) -> None:
    config_file = tmp_path / "database_types.json"
    _write_config(config_file)

    config = load_database_type_config(config_file)

    assert config["metadata"]["supported_db_types"] == ["mariadb"]
    assert config["database_types"]["mariadb"]["name"] == "MariaDB"


def test_load_database_type_config_raises_clear_errors(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.json"
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Archivo de configuración no encontrado"):
        load_database_type_config(missing_file)

    with pytest.raises(ValueError, match="Error al leer archivo JSON"):
        load_database_type_config(invalid_file)


def test_database_type_validator_reload_uses_separate_loader(tmp_path: Path) -> None:
    config_file = tmp_path / "database_types.json"
    _write_config(config_file, db_name="MariaDB")
    validator = DatabaseTypeValidator(config_file=config_file)

    assert validator.get_db_type_name("mariadb") == "MariaDB"

    _write_config(config_file, db_name="MariaDB Enterprise")
    validator.reload_config()

    assert validator.get_db_type_name("mariadb") == "MariaDB Enterprise"
    assert validator.get_error_message("unknown", code=7) == "Error 7"
