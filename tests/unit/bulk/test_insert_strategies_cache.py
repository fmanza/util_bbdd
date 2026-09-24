"""Tests para verificar optimización de caching de SQL template en MySQLMultiRowInsertStrategy."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert, text

from util_bbdd.bulk._execution.batch import MySQLMultiRowInsertStrategy

# ============================================================================
# Helpers
# ============================================================================


def _make_table() -> Table:
    return Table(
        "test_table",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(100)),
        Column("value", Integer),
    )


# ============================================================================
# Tests de caching
# ============================================================================


class TestMySQLMultiRowInsertStrategyCache:
    """Verifica que MySQLMultiRowInsertStrategy cachea templates SQL."""

    def test_cache_is_initialized_empty(self) -> None:
        """El caché debe inicializarse vacío."""
        strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=1000)
        assert len(strategy._sql_template_cache) == 0

    def test_template_is_cached_after_first_call(self) -> None:
        """Después de la primera ejecución, el template debe estar en caché."""
        engine = create_engine("sqlite:///:memory:")
        connection = engine.connect()
        connection.exec_driver_sql("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")

        strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=1000)
        table = _make_table()
        stmt = insert(table)

        records = [
            {"id": 1, "name": "row_1", "value": 10},
            {"id": 2, "name": "row_2", "value": 20},
            {"id": 3, "name": "row_3", "value": 30},
        ]

        # Primera ejecución
        strategy.execute(connection=connection, stmt=stmt, records=records)

        # El caché debe contener una entrada: (3 filas, tabla, ("id", "name", "value"))
        cache_key = (3, "test_table", ("id", "name", "value"))
        assert cache_key in strategy._sql_template_cache, f"Esperaba cache_key {cache_key} en caché, pero no existe"

        connection.close()

    def test_multiple_different_batch_sizes_cached_separately(self) -> None:
        """Diferentes tamaños de batch deben cachearse por separado."""
        engine = create_engine("sqlite:///:memory:")
        connection = engine.connect()
        connection.exec_driver_sql("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")

        strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=100)  # max 100
        table = _make_table()
        stmt = insert(table)

        # Batch 1: 3 filas
        records_1 = [{"id": i, "name": f"row_{i}", "value": i * 10} for i in range(1, 4)]
        strategy.execute(connection=connection, stmt=stmt, records=records_1)

        # Batch 2: 5 filas
        records_2 = [{"id": i, "name": f"row_{i}", "value": i * 10} for i in range(10, 15)]
        strategy.execute(connection=connection, stmt=stmt, records=records_2)

        # Caché debe tener 2 entradas: (3, ...) y (5, ...)
        assert len(strategy._sql_template_cache) == 2

        cache_keys = list(strategy._sql_template_cache.keys())
        sizes = {key[0] for key in cache_keys}
        assert sizes == {3, 5}, f"Esperaba sizes {{3, 5}}, pero obtuve {sizes}"

        connection.close()

    def test_same_batch_size_reuses_cache_template(self) -> None:
        """El mismo tamaño de batch debe reutilizar el template del caché."""
        engine = create_engine("sqlite:///:memory:")
        connection = engine.connect()
        connection.exec_driver_sql("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")

        strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=100)
        table = _make_table()
        stmt = insert(table)

        # Mock text() para contar cuántas veces se llama
        original_text = text
        call_count = 0

        def mock_text(sql_str: str) -> Any:
            nonlocal call_count
            call_count += 1
            return original_text(sql_str)

        with patch("util_bbdd.bulk._execution.batch.text", side_effect=mock_text):
            # Batch 1: 3 filas
            records_1 = [{"id": i, "name": f"row_{i}", "value": i * 10} for i in range(1, 4)]
            strategy.execute(connection=connection, stmt=stmt, records=records_1)

            # Batch 2: 3 filas (mismo tamaño)
            records_2 = [{"id": i, "name": f"row_{i}", "value": i * 10} for i in range(10, 13)]
            strategy.execute(connection=connection, stmt=stmt, records=records_2)

        # text() debe llamarse 2 veces (una por cada execute)
        # aunque el template sea el mismo, porque execute siempre llama a text()
        # Lo importante es que el template SQL no se reconstruyó (está en caché)
        assert len(strategy._sql_template_cache) == 1, "Debe haber solo 1 entrada de caché (mismo tamaño de batch)"

        connection.close()

    def test_build_sql_template_returns_correct_template(self) -> None:
        """_build_sql_template debe construir un template válido."""
        strategy = MySQLMultiRowInsertStrategy()

        template = strategy._build_sql_template(
            num_rows=2,
            cols=["id", "name"],
            quoted_table="test_table",
            quoted_cols="id, name",
        )

        # Template debe tener estructura: INSERT INTO ... VALUES (...), (...)
        assert "INSERT INTO test_table (id, name) VALUES" in template
        assert ":p0_0" in template  # Placeholder para fila 0, col 0
        assert ":p0_1" in template  # Placeholder para fila 0, col 1
        assert ":p1_0" in template  # Placeholder para fila 1, col 0
        assert ":p1_1" in template  # Placeholder para fila 1, col 1

    def test_template_cached_after_build(self) -> None:
        """Después de llamar _build_sql_template, debe estar en caché."""
        strategy = MySQLMultiRowInsertStrategy()

        # Primera llamada
        template1 = strategy._build_sql_template(
            num_rows=3,
            cols=["x", "y", "z"],
            quoted_table="t1",
            quoted_cols="x, y, z",
        )

        # El caché debe tener una entrada
        cache_key = (3, "t1", ("x", "y", "z"))
        assert cache_key in strategy._sql_template_cache

        # Segunda llamada con los mismos parámetros
        template2 = strategy._build_sql_template(
            num_rows=3,
            cols=["x", "y", "z"],
            quoted_table="t1",
            quoted_cols="x, y, z",
        )

        # Los templates deben ser idénticos (retornados del caché)
        assert template1 == template2
        assert template1 is template2  # Mismo objeto del caché

    def test_cache_does_not_interfere_with_different_columns(self) -> None:
        """Diferentes sets de columnas deben cachearse por separado."""
        strategy = MySQLMultiRowInsertStrategy()

        template1 = strategy._build_sql_template(
            num_rows=2,
            cols=["a", "b"],
            quoted_table="t",
            quoted_cols="a, b",
        )

        template2 = strategy._build_sql_template(
            num_rows=2,
            cols=["a", "b", "c"],
            quoted_table="t",
            quoted_cols="a, b, c",
        )

        # Los templates deben ser diferentes
        assert template1 != template2
        # Y ambos deben estar en caché
        assert len(strategy._sql_template_cache) == 2


# ============================================================================
# Tests de funcionalidad (sin cambios esperados)
# ============================================================================


class TestMySQLMultiRowInsertStrategyFunctionality:
    """Verifica que la funcionalidad siga siendo correcta después de la optimización."""

    def test_execute_with_cache_produces_correct_results(self) -> None:
        """La ejecución con caché debe producir los mismos resultados."""
        engine = create_engine("sqlite:///:memory:")
        connection = engine.connect()
        connection.exec_driver_sql("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")

        strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=10)
        table = _make_table()
        stmt = insert(table)

        records = [{"id": i, "name": f"row_{i:03d}", "value": i * 10} for i in range(1, 101)]

        # Ejecutar con caché
        strategy.execute(connection=connection, stmt=stmt, records=records)

        # Verificar que los datos fueron insertados correctamente
        count = connection.execute(text("SELECT COUNT(*) FROM test_table")).scalar()
        assert count == 100, f"Esperaba 100 filas, pero se insertaron {count}"

        # Verificar que los datos son correctos
        result = connection.execute(text("SELECT SUM(value) FROM test_table")).scalar()
        expected_sum = sum(i * 10 for i in range(1, 101))
        assert result == expected_sum, f"Suma esperada {expected_sum}, pero obtuve {result}"

        connection.close()

    def test_empty_records_handled_correctly(self) -> None:
        """Records vacío debe ser manejado sin error."""
        engine = create_engine("sqlite:///:memory:")
        connection = engine.connect()
        connection.exec_driver_sql("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")

        strategy = MySQLMultiRowInsertStrategy()
        table = _make_table()
        stmt = insert(table)

        # Ejecutar con records vacío
        strategy.execute(connection=connection, stmt=stmt, records=[])

        # Debe no lanzar error, y caché debe seguir vacío
        count = connection.execute(text("SELECT COUNT(*) FROM test_table")).scalar()
        assert count == 0

        connection.close()

    def test_text_clause_fallback_works(self) -> None:
        """Si stmt es TextClause, debe caer a ejecución estándar."""
        engine = create_engine("sqlite:///:memory:")
        connection = engine.connect()
        connection.exec_driver_sql("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")

        strategy = MySQLMultiRowInsertStrategy()

        # TextClause (no tiene atributo .table)
        text_stmt = text("INSERT INTO test_table (id, name) VALUES (:id, :name)")

        records = [
            {"id": 1, "name": "a"},
            {"id": 2, "name": "b"},
        ]

        # Debe usar fallback (DefaultInsertStrategy)
        strategy.execute(connection=connection, stmt=text_stmt, records=records)

        count = connection.execute(text("SELECT COUNT(*) FROM test_table")).scalar()
        assert count == 2

        connection.close()


# ============================================================================
# P-22: la caché no debe mezclar tablas con las mismas columnas
# ============================================================================


class TestMySQLMultiRowInsertStrategyCachePerTable:
    """P-22 (performance-audit de bulk, 2026-09-24): la clave de caché no incluía la tabla.

    Una misma instancia (p.ej. la ``BulkCrud`` compartida del volcado secuencial) que insertaba en dos tablas con las
    mismas columnas y el mismo tamaño de sub-lote reutilizaba la plantilla de la primera tabla: las filas de la segunda
    acababan en la primera, sin error.
    """

    def test_same_columns_different_tables_get_distinct_templates(self) -> None:
        strategy = MySQLMultiRowInsertStrategy()

        template_a = strategy._build_sql_template(num_rows=2, cols=["id", "v"], quoted_table="a", quoted_cols="id, v")
        template_b = strategy._build_sql_template(num_rows=2, cols=["id", "v"], quoted_table="b", quoted_cols="id, v")

        assert template_a.startswith("INSERT INTO a ")
        assert template_b.startswith("INSERT INTO b ")
        assert len(strategy._sql_template_cache) == 2

    def test_rows_land_in_their_own_table(self) -> None:
        engine = create_engine("sqlite://")
        metadata = MetaData()
        table_a = Table("a", metadata, Column("id", Integer, primary_key=True), Column("v", String(10)))
        table_b = Table("b", metadata, Column("id", Integer, primary_key=True), Column("v", String(10)))
        metadata.create_all(engine)
        strategy = MySQLMultiRowInsertStrategy()

        with engine.begin() as conn:
            strategy.execute(
                connection=conn, stmt=insert(table_a), records=[{"id": 1, "v": "a1"}, {"id": 2, "v": "a2"}]
            )
            strategy.execute(
                connection=conn, stmt=insert(table_b), records=[{"id": 3, "v": "b3"}, {"id": 4, "v": "b4"}]
            )

        with engine.connect() as conn:
            rows_a = conn.execute(text("SELECT id, v FROM a ORDER BY id")).all()
            rows_b = conn.execute(text("SELECT id, v FROM b ORDER BY id")).all()
        assert [tuple(r) for r in rows_a] == [(1, "a1"), (2, "a2")]
        assert [tuple(r) for r in rows_b] == [(3, "b3"), (4, "b4")]
