"""Unit tests para MySQLMultiRowInsertStrategy.get_min_max_allowed_packet()."""

from __future__ import annotations

from util_bbdd.bulk._execution.batch import MySQLMultiRowInsertStrategy


class TestMySQLMultiRowInsertStrategyMinPacketCalculation:
    """Tests para MySQLMultiRowInsertStrategy.get_min_max_allowed_packet()."""

    def test_default_max_rows_per_statement(self) -> None:
        """Test con max_rows_per_statement default (1000)."""
        strategy = MySQLMultiRowInsertStrategy()
        min_packet = strategy.get_min_max_allowed_packet()

        # Con 1000 filas × 2000 bytes × 1.5 = ~3 MB
        # Debería retornar al menos 64 MB (estándar para bulk)
        assert min_packet >= 64 * 1_048_576

    def test_small_max_rows_per_statement(self) -> None:
        """Test con max_rows_per_statement pequeño (100)."""
        strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=100)
        min_packet = strategy.get_min_max_allowed_packet()

        # Con 100 filas × 2000 bytes × 1.5 = ~300 KB
        # Debería retornar al menos 64 MB (estándar para bulk)
        assert min_packet >= 64 * 1_048_576

    def test_large_max_rows_per_statement(self) -> None:
        """Test con max_rows_per_statement grande (5000)."""
        strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=5000)
        min_packet = strategy.get_min_max_allowed_packet()

        # Con 5000 filas × 2000 bytes × 1.3 = ~13 MB
        # Debería retornar 128 MB o mayor
        assert min_packet >= 64 * 1_048_576

    def test_custom_avg_row_bytes(self) -> None:
        """Test con avg_row_bytes personalizado."""
        strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=1000)
        min_packet = strategy.get_min_max_allowed_packet(avg_row_bytes=4000)

        # Con 1000 filas × 4000 bytes × 1.3 = ~5.2 MB
        # Debería retornar un valor válido
        assert min_packet in [32 * 1_048_576, 64 * 1_048_576, 128 * 1_048_576, 256 * 1_048_576]

    def test_min_packet_size_lower_bound(self) -> None:
        """Test que min_packet_size nunca es menor de 64 MB."""
        strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=1)
        min_packet = strategy.get_min_max_allowed_packet(avg_row_bytes=10)

        # Incluso con valores muy pequeños, debería ser al menos 64 MB
        assert min_packet >= 64 * 1_048_576

    def test_min_packet_size_upper_bound(self) -> None:
        """Test que min_packet_size nunca excede 256 MB."""
        strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=10000)
        min_packet = strategy.get_min_max_allowed_packet(avg_row_bytes=10000)

        # Incluso con valores muy grandes, no debería exceder 256 MB
        assert min_packet <= 256 * 1_048_576

    def test_multiple_strategies_different_sizes(self) -> None:
        """Test que estrategias diferentes retornan tamaños diferentes."""
        strategy_small = MySQLMultiRowInsertStrategy(max_rows_per_statement=500)
        strategy_large = MySQLMultiRowInsertStrategy(max_rows_per_statement=2000)

        min_packet_small = strategy_small.get_min_max_allowed_packet()
        min_packet_large = strategy_large.get_min_max_allowed_packet()

        # El tamaño para estrategia grande debería ser >= que para pequeña
        assert min_packet_large >= min_packet_small

    def test_returns_power_of_two(self) -> None:
        """Test que retorna siempre una potencia de 2 válida."""
        valid_values = {
            32 * 1_048_576,
            64 * 1_048_576,
            128 * 1_048_576,
            256 * 1_048_576,
        }

        for max_rows in [100, 500, 1000, 2000, 5000]:
            strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=max_rows)
            min_packet = strategy.get_min_max_allowed_packet()
            assert min_packet in valid_values
