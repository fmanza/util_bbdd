"""Tests del fallback de DDL MariaDB cuando SHOW CREATE TABLE falla por decode."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.database_exceptions import DatabaseOperationError
from util_bbdd.managers import DatabaseManager
from util_bbdd.metadata import DatabaseMetadataCache


def _build_wrapped_decode_error() -> DatabaseOperationError:
    try:
        raise UnicodeDecodeError("utf-8", b"\xd3", 0, 1, "invalid continuation byte")
    except UnicodeDecodeError as decode_err:
        try:
            raise SystemError(
                "<method 'fetchone' of 'mariadb.cursor' objects> returned a result with an exception set"
            ) from decode_err
        except SystemError as driver_err:
            try:
                raise DatabaseOperationError(
                    "Error executing query create_table", "SELECT", db_type="mariadb"
                ) from driver_err
            except DatabaseOperationError as operation_err:
                return operation_err


class TestDatabaseManagerGetDdlFallback:
    def _build_manager(self) -> DatabaseManager:
        manager = DatabaseManager.__new__(DatabaseManager)
        manager.db_type = "mariadb"
        manager.database = "db"
        manager.conn_params = {"database": "db"}
        manager.logger = MagicMock()
        manager.db_cache = DatabaseMetadataCache()
        return manager

    def test_get_ddl_fallbacks_to_metadata_when_show_create_has_decode_error(self) -> None:
        manager = self._build_manager()
        decode_error = _build_wrapped_decode_error()
        manager._execute_metadata_one = MagicMock(side_effect=decode_error)
        manager.get_columns = MagicMock(
            return_value=[
                ("id", "int", "NO", "PRI", None, "auto_increment", ""),
                ("name", "varchar(50)", "YES", "", "Óscar", "", ""),
            ]
        )
        manager.get_primary_keys = MagicMock(return_value=[("id",)])

        ddl = manager.get_ddl("users")

        assert ddl.startswith("CREATE TABLE `users`")
        assert "`id` int NOT NULL auto_increment" in ddl
        assert "`name` varchar(50) NULL DEFAULT 'Óscar'" in ddl
        assert "PRIMARY KEY (`id`)" in ddl
        manager._execute_metadata_one.assert_called_once()
        manager.get_columns.assert_called_once_with("users")
        manager.get_primary_keys.assert_called_once_with("users")

    def test_get_ddl_reraises_non_decode_database_error(self) -> None:
        manager = self._build_manager()
        manager._execute_metadata_one = MagicMock(
            side_effect=DatabaseOperationError("Error distinto", "SELECT", db_type="mariadb")
        )
        manager.get_columns = MagicMock(return_value=[("id", "int", "NO", "PRI", None, "", "")])
        manager.get_primary_keys = MagicMock(return_value=[("id",)])

        with pytest.raises(DatabaseOperationError, match="Error distinto"):
            manager.get_ddl("users")

        manager.get_columns.assert_not_called()
        manager.get_primary_keys.assert_not_called()

    def test_get_columns_uses_safe_fallback_when_metadata_decode_fails(self) -> None:
        manager = self._build_manager()
        decode_error = _build_wrapped_decode_error()
        manager._execute_metadata_many = MagicMock(side_effect=decode_error)
        manager.execute_custom_many = MagicMock(
            return_value=[
                ("6964", "696e74", "NO", "PRI", 1, None, "6175746f5f696e6372656d656e74", ""),
                ("6e616d65", "7661726368617228353029", "YES", "", 0, "d373636172", "", "436f6c756d6e6120d3"),
            ]
        )

        columns = manager.get_columns("users")

        assert columns == [
            ("id", "int", "NO", "PRI", None, "auto_increment", ""),
            ("name", "varchar(50)", "YES", "", "Óscar", "", "Columna Ó"),
        ]
        manager._execute_metadata_many.assert_called_once()
        manager.execute_custom_many.assert_called_once()
