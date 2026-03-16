"""Tests de las rutas seguras de metadatos MariaDB para evitar errores de decode."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.managers import SyncDatabaseManager
from util_bbdd.metadata import DatabaseMetadataCache


class TestDatabaseManagerMariaDbMetadataPaths:
    def _build_manager(self) -> SyncDatabaseManager:
        manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
        manager.db_type = "mariadb"
        manager.database = "db"
        manager.conn_params = {"database": "db"}
        manager.logger = MagicMock()
        manager.db_cache = DatabaseMetadataCache()
        return manager

    def test_get_ddl_uses_metadata_builder_as_primary_path(self) -> None:
        manager = self._build_manager()
        manager._execute_metadata_one = MagicMock()
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
        manager._execute_metadata_one.assert_not_called()
        manager.get_columns.assert_called_once_with("users")
        manager.get_primary_keys.assert_called_once_with("users")

    def test_get_routine_ddl_uses_information_schema_as_primary_path(self) -> None:
        manager = self._build_manager()
        manager._execute_metadata_one = MagicMock()
        manager._execute_metadata_many = MagicMock(
            side_effect=[
                [
                    (
                        "52454d4f5645525f4143454e544f53",
                        "FUNCTION",
                        "46756e6369c3b36e20646520707275656261",
                        "726f6f74406c6f63616c686f7374",
                        "444546494e4552",
                        "4d4f4449464945532053514c2044415441",
                        "NO",
                        "766172636861722832353529",
                        "",
                        "424547494e2052455455524e20276f6b273b20454e44",
                    )
                ],
                [
                    (
                        "RETURN",
                        "RETURN_VALUE",
                        "FUNCTION",
                        "52454d4f5645525f4143454e544f53",
                        "766172636861722832353529",
                        "757466386d6233",
                        "757466386d62335f62696e",
                        0,
                    ),
                    (
                        "494e",
                        "705f74657874",
                        "FUNCTION",
                        "52454d4f5645525f4143454e544f53",
                        "766172636861722832353529",
                        "",
                        "",
                        1,
                    ),
                ],
            ]
        )

        ddl = manager.get_routine_ddl("REMOVER_ACENTOS", "FUNCTION")

        assert ddl.startswith(
            "CREATE DEFINER=`root`@`localhost` FUNCTION `db`.`REMOVER_ACENTOS`(p_text varchar(255)) "
            "RETURNS varchar(255) CHARSET utf8mb3 COLLATE utf8mb3_bin"
        )
        assert "IN p_text varchar(255)" not in ddl
        assert "MODIFIES SQL DATA" not in ddl
        assert "SQL SECURITY DEFINER" not in ddl
        assert "COMMENT 'Función de prueba'" in ddl
        assert manager._execute_metadata_many.call_count == 2
        manager._execute_metadata_one.assert_not_called()
        assert manager._execute_metadata_many.call_args_list[0].args[0] == "rutinas_mariadb_detalle"
        assert manager._execute_metadata_many.call_args_list[1].args[0] == "parametros_rutinas_mariadb_detalle"

    def test_get_columns_uses_hex_safe_metadata_query_as_primary_path(self) -> None:
        manager = self._build_manager()
        manager._execute_metadata_many = MagicMock()
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
        manager._execute_metadata_many.assert_not_called()
        manager.execute_custom_many.assert_called_once()
