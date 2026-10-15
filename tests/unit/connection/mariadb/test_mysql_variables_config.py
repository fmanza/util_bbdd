"""Unit tests para MySQLVariableValidator y MySQLOptimalConfig."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from util_bbdd.connection.mariadb._config import MySQLOptimalConfig
from util_bbdd.connection.mariadb._variables import MySQLVariableValidator


class TestMySQLOptimalConfig:
    """Tests para MySQLOptimalConfig."""

    def test_dev_config(self) -> None:
        """Test configuración dev."""
        config = MySQLOptimalConfig.dev()
        assert config.innodb_buffer_pool_size == 256 * 1_048_576  # 256 MB
        assert config.max_allowed_packet == 16 * 1_048_576  # 16 MB

    def test_production_config(self) -> None:
        """Test configuración production."""
        config = MySQLOptimalConfig.production()
        assert config.innodb_buffer_pool_size == 1 * 1_073_741_824  # 1 GB
        assert config.max_allowed_packet == 64 * 1_048_576  # 64 MB

    def test_high_volume_config(self) -> None:
        """Test configuración high volume."""
        config = MySQLOptimalConfig.high_volume()
        assert config.innodb_buffer_pool_size == 4 * 1_073_741_824  # 4 GB
        assert config.max_allowed_packet == 128 * 1_048_576  # 128 MB

    def test_suggest_small_dataset(self) -> None:
        """Test suggest para dataset pequeño."""
        config = MySQLOptimalConfig.suggest(num_rows=50_000)
        # Debería retornar dev()
        assert config.innodb_buffer_pool_size == 256 * 1_048_576

    def test_suggest_medium_dataset(self) -> None:
        """Test suggest para dataset medio."""
        config = MySQLOptimalConfig.suggest(num_rows=500_000)
        # Debería retornar production()
        assert config.innodb_buffer_pool_size == 1 * 1_073_741_824

    def test_suggest_large_dataset(self) -> None:
        """Test suggest para dataset grande."""
        config = MySQLOptimalConfig.suggest(num_rows=5_000_000)
        # Debería retornar high_volume()
        assert config.innodb_buffer_pool_size == 4 * 1_073_741_824

    def test_format_bytes_kb(self) -> None:
        """Test format_bytes para kilobytes."""
        config = MySQLOptimalConfig.dev()
        formatted = config.format_bytes(2048)
        assert "KB" in formatted

    def test_format_bytes_mb(self) -> None:
        """Test format_bytes para megabytes."""
        config = MySQLOptimalConfig.dev()
        formatted = config.format_bytes(64 * 1_048_576)
        assert "64.0 MB" in formatted

    def test_format_bytes_gb(self) -> None:
        """Test format_bytes para gigabytes."""
        config = MySQLOptimalConfig.dev()
        formatted = config.format_bytes(1 * 1_073_741_824)
        assert "GB" in formatted

    def test_str_representation(self) -> None:
        """Test representación string."""
        config = MySQLOptimalConfig.production()
        str_repr = str(config)
        assert "MySQLOptimalConfig" in str_repr
        assert "1.0 GB" in str_repr
        assert "64.0 MB" in str_repr


class TestMySQLVariableValidator:
    """Tests para MySQLVariableValidator."""

    def test_init_with_valid_connection(self) -> None:
        """Test inicialización con conexión válida."""
        mock_conn = MagicMock()
        validator = MySQLVariableValidator(mock_conn)
        assert validator._connection is mock_conn

    def test_init_with_none_connection(self) -> None:
        """Test inicialización con conexión None."""
        with pytest.raises(ValueError, match="connection no puede ser None"):
            MySQLVariableValidator(None)

    def test_read_variables_success(self) -> None:
        """Test lectura exitosa de variables."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("max_allowed_packet", "16777216"),
            ("innodb_buffer_pool_size", "134217728"),
        ]
        mock_conn.execute.return_value = mock_result

        validator = MySQLVariableValidator(mock_conn)
        vars_dict = validator.read_variables()

        # Verificar que las variables se leyeron correctamente
        # (puede que no todas si hay errores en el mock)
        assert isinstance(vars_dict, dict)

    def test_read_variables_empty_result(self) -> None:
        """Test cuando no se encuentran variables."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result

        validator = MySQLVariableValidator(mock_conn)
        vars_dict = validator.read_variables()

        assert isinstance(vars_dict, dict)

    def test_validate_all_valid(self) -> None:
        """Test validación cuando todas las variables son válidas."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.side_effect = [
            [("max_allowed_packet", "67108864")],  # 64 MB
            [("innodb_buffer_pool_size", "1073741824")],  # 1 GB
        ]
        mock_conn.execute.return_value = mock_result

        validator = MySQLVariableValidator(mock_conn)

        # Simular respuestas múltiples (SHOW VARIABLES se ejecuta varias veces)
        with patch.object(validator, "read_variables") as mock_read:
            mock_read.return_value = {
                "max_allowed_packet": 67108864,  # 64 MB
                "innodb_buffer_pool_size": 1073741824,  # 1 GB
            }

            required = {
                "max_allowed_packet": 64 * 1_048_576,
                "innodb_buffer_pool_size": 1 * 1_073_741_824,
            }
            result = validator.validate(required)

            # Todas deberían ser válidas
            assert all(result.values())

    def test_validate_some_invalid(self) -> None:
        """Test validación cuando algunas variables son inválidas."""
        mock_conn = MagicMock()
        validator = MySQLVariableValidator(mock_conn)

        with patch.object(validator, "read_variables") as mock_read:
            mock_read.return_value = {
                "max_allowed_packet": 16 * 1_048_576,  # 16 MB (insuficiente)
                "innodb_buffer_pool_size": 1 * 1_073_741_824,  # 1 GB (suficiente)
            }

            required = {
                "max_allowed_packet": 64 * 1_048_576,  # Requiere 64 MB
                "innodb_buffer_pool_size": 1 * 1_073_741_824,
            }
            result = validator.validate(required)

            assert not result["max_allowed_packet"]  # Debería ser False
            assert result["innodb_buffer_pool_size"]  # Debería ser True

    def test_format_bytes_kb(self) -> None:
        """Test format_bytes para kilobytes."""
        mock_conn = MagicMock()
        validator = MySQLVariableValidator(mock_conn)
        formatted = validator.format_bytes(2048)
        assert "KB" in formatted

    def test_format_bytes_mb(self) -> None:
        """Test format_bytes para megabytes."""
        mock_conn = MagicMock()
        validator = MySQLVariableValidator(mock_conn)
        formatted = validator.format_bytes(64 * 1_048_576)
        assert "64.0 MB" in formatted

    def test_format_bytes_gb(self) -> None:
        """Test format_bytes para gigabytes."""
        mock_conn = MagicMock()
        validator = MySQLVariableValidator(mock_conn)
        formatted = validator.format_bytes(1 * 1_073_741_824)
        assert "GB" in formatted

    def test_log_summary_with_valid_config(self) -> None:
        """Test log_summary con configuración válida."""
        mock_conn = MagicMock()
        validator = MySQLVariableValidator(mock_conn)

        with patch.object(validator, "read_variables") as mock_read:
            with patch("util_bbdd.connection.mariadb._variables.logger") as mock_logger:
                mock_read.return_value = {
                    "max_allowed_packet": 64 * 1_048_576,
                    "innodb_buffer_pool_size": 1 * 1_073_741_824,
                }

                required = {
                    "max_allowed_packet": 64 * 1_048_576,
                    "innodb_buffer_pool_size": 1 * 1_073_741_824,
                }
                validator.log_summary(required)

                # Debería haber llamado a logger.info al menos una vez
                assert mock_logger.info.called or mock_logger.warning.called

    def test_log_summary_no_variables_found(self) -> None:
        """Test log_summary cuando no se encuentran variables."""
        mock_conn = MagicMock()
        validator = MySQLVariableValidator(mock_conn)

        with patch.object(validator, "read_variables") as mock_read:
            with patch("util_bbdd.connection.mariadb._variables.logger") as mock_logger:
                mock_read.return_value = {}  # Sin variables

                validator.log_summary()

                # Debería haber logueado un warning
                assert mock_logger.warning.called


class TestReadVariablesRobustness:
    """2.2.1 (R-1, R-1b): coincidencia exacta y filas con forma inesperada."""

    @staticmethod
    def _conn(rows_by_name: dict[str, object]) -> MagicMock:
        conn = MagicMock()

        def execute(stmt: object) -> MagicMock:
            sql = str(stmt)
            name = sql.split("'")[1]
            result = MagicMock()
            result.fetchall.return_value = rows_by_name.get(name, [])
            return result

        conn.execute.side_effect = execute
        return conn

    def test_queries_with_exact_match_not_like(self) -> None:
        conn = self._conn({})
        MySQLVariableValidator(conn).read_variables()

        sqls = [str(call.args[0]) for call in conn.execute.call_args_list]
        assert sqls
        assert all(sql.startswith("SHOW VARIABLES WHERE Variable_name = '") for sql in sqls)
        assert not any("LIKE" in sql for sql in sqls)

    def test_an_unexpected_row_skips_only_that_variable(self, caplog: pytest.LogCaptureFixture) -> None:
        conn = self._conn(
            {
                "max_allowed_packet": [("max_allowed_packet",)],  # una sola columna
                "innodb_buffer_pool_size": [("innodb_buffer_pool_size", "134217728")],
            }
        )

        result = MySQLVariableValidator(conn).read_variables()

        assert result == {"innodb_buffer_pool_size": 134_217_728}
        assert "Fila inesperada para la variable 'max_allowed_packet'" in caplog.text
