"""HSQLDB en red: conexión nativa de la librería (jaydebeapi) contra un servidor HSQLDB (H1, 2026-10-09).

Requiere el servicio de ``docker-compose.bench-hsqldb.yml`` y, en el cliente, el mismo jar y Java (``JAVA_HOME`` si
JPype no encuentra ``jvm.dll``). Se salta si falta alguno::

    docker compose -f docker-compose.bench.yml -f docker-compose.bench-hsqldb.yml up -d --wait hsqldb
    UTIL_BBDD_TEST_HSQLDB_JAR=build/bench_hsqldb/hsqldb-2.7.4.jar \\
    UTIL_BBDD_TEST_HSQLDB_SERVER_URL=jdbc:hsqldb:hsql://127.0.0.1:59001/bench \\
        python -m pytest tests/integration/test_hsqldb_server.py
"""

from __future__ import annotations

import importlib.util
import os
import uuid

from collections.abc import Iterator
from typing import Any

import pytest

from util_bbdd import SyncDatabaseManager

JAR_ENV = "UTIL_BBDD_TEST_HSQLDB_JAR"
URL_ENV = "UTIL_BBDD_TEST_HSQLDB_SERVER_URL"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get(JAR_ENV), reason=f"{JAR_ENV} no definida"),
    pytest.mark.skipif(not os.environ.get(URL_ENV), reason=f"{URL_ENV} no definida"),
    pytest.mark.skipif(importlib.util.find_spec("jaydebeapi") is None, reason="jaydebeapi no instalado"),
]


def _params(**extra: Any) -> dict[str, Any]:
    return {
        "user": "SA",
        "password": "",
        "jdbc_url": os.environ[URL_ENV],
        "jdbc_jar": os.environ[JAR_ENV],
        **extra,
    }


@pytest.fixture
def table() -> Iterator[str]:
    name = f"ZZ_UTIL_BBDD_H1_{uuid.uuid4().hex[:8].upper()}"
    manager = SyncDatabaseManager("hsqldb", _params())
    connection = manager.get_connection()
    cursor = connection.cursor()
    cursor.execute(f"CREATE TABLE {name} (ID INTEGER PRIMARY KEY, NOMBRE VARCHAR(40))")
    cursor.execute(f"COMMENT ON TABLE {name} IS 'tabla de prueba H1'")
    cursor.execute(f"INSERT INTO {name} VALUES (1, 'ñandú')")
    cursor.close()
    manager.close()
    try:
        yield name
    finally:
        manager = SyncDatabaseManager("hsqldb", _params())
        cursor = manager.get_connection().cursor()
        cursor.execute(f"DROP TABLE {name} IF EXISTS")
        cursor.close()
        manager.close()


def test_native_connection_reads_data(table: str) -> None:
    manager = SyncDatabaseManager("hsqldb", _params())
    try:
        cursor = manager.get_connection().cursor()
        cursor.execute(f"SELECT NOMBRE FROM {table} WHERE ID = 1")
        assert cursor.fetchone()[0] == "ñandú"
        cursor.close()
    finally:
        manager.close()


def test_metadata_snapshot_sees_table_and_comment(table: str) -> None:
    manager = SyncDatabaseManager("hsqldb", _params())
    try:
        snapshot = manager.get_schema_metadata()
        tables = {t.name: t for t in snapshot.tables()}
        assert table in tables
        assert tables[table].comment == "tabla de prueba H1"
        assert [c.name for c in snapshot.columns(table)] == ["ID", "NOMBRE"]
    finally:
        manager.close()


def test_creation_only_properties_do_not_apply_to_existing_server_database() -> None:
    """``connection_properties`` llega como propiedad JDBC (la autenticación viaja igual), pero ``sql.syntax_ora`` solo
    actúa al crear la base de datos: en memoria la crea la conexión; en un servidor ya existe y se ignora."""
    manager = SyncDatabaseManager("hsqldb", _params(connection_properties={"sql.syntax_ora": "true"}))
    try:
        cursor = manager.get_connection().cursor()
        cursor.execute("VALUES 1")  # la conexión con propiedades extra funciona
        assert cursor.fetchone()[0] == 1
        with pytest.raises(Exception, match="DUAL"):
            cursor.execute("SELECT 1 FROM DUAL")
        cursor.close()
    finally:
        manager.close()


def test_table_ddl_lists_columns_in_order(table: str) -> None:
    """B-04 (v0.41.1): ``LISTAGG`` sin ``WITHIN GROUP`` y la rama de ``INFORMATION_SCHEMA.VIEWS.TEXT`` (columna que no
    existe en HSQLDB 2.7) hacían fallar ``get_ddl``; el ``CASE`` de nulabilidad rellenaba el tipo con espacios."""
    manager = SyncDatabaseManager("hsqldb", _params())
    try:
        # ID se declaró PRIMARY KEY sin NOT NULL: HSQLDB informa IS_NULLABLE = YES (sin PK en el DDL: limitación conocida)
        assert manager.get_ddl(table) == f"CREATE TABLE {table} (ID INTEGER, NOMBRE CHARACTER VARYING(40))"
        assert manager.get_ddl("ZZ_NO_EXISTE") == ""
        other = f"{table}_B"
        cursor = manager.get_connection().cursor()
        cursor.execute(f"CREATE TABLE {other} (A INTEGER NOT NULL, B VARCHAR(5) DEFAULT 'x' NOT NULL, C DATE)")
        cursor.close()
        try:
            expected = f"CREATE TABLE {other} (A INTEGER NOT NULL, B CHARACTER VARYING(5) NOT NULL DEFAULT 'x', C DATE)"
            assert manager.get_ddl(other) == expected
        finally:
            cursor = manager.get_connection().cursor()
            cursor.execute(f"DROP TABLE {other} IF EXISTS")
            cursor.close()
    finally:
        manager.close()


def test_documentation_with_table_ddl(table: str, tmp_path: Any) -> None:
    from util_bbdd.doc import DatabaseDocumentation

    manager = SyncDatabaseManager("hsqldb", _params())
    try:
        result = DatabaseDocumentation(
            manager,
            directorio_salida=tmp_path,
            imprimir={"tablas": {"imprimir_tablas": True, "ddl": True, "columnas": True}},
            formatos=["html"],
        ).generate()
    finally:
        manager.close()
    pages = " ".join(page.read_text(encoding="utf-8") for page in (result.outputs["html"] / "tables").glob("*.html"))
    assert f"CREATE TABLE {table} (ID INTEGER, NOMBRE" in pages
