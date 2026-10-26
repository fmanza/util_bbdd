"""U-V6 (G34 de util_bbdd_web): ``error_msg`` del volcado sin parámetros de SQLAlchemy ni valores de las filas."""

from __future__ import annotations

from pathlib import Path

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from util_bbdd.dump import DumpConfig, DumpOrchestrator
from util_bbdd.dump._sql_utils import error_message

pytestmark = pytest.mark.unit

SQL = "INSERT INTO clientes (id, nombre) VALUES (%(id)s, %(nombre)s)"
PARAMS = {"id": 1, "nombre": "Ana Secreta"}


def _wrapped(driver_message: str) -> IntegrityError:
    """Error de SQLAlchemy como lo da un driver: con la sentencia y los parámetros (filas del origen)."""
    return IntegrityError(SQL, PARAMS, Exception(driver_message))


@pytest.mark.parametrize(
    ("driver_message", "expected"),
    [
        pytest.param(
            "(1062, \"Duplicate entry 'Ana O'Brien' for key 'clientes.PRIMARY'\")",
            "(1062, \"Duplicate entry '…' for key 'clientes.PRIMARY'\")",
            id="mysql-duplicado",
        ),
        pytest.param(
            "(1366, \"Incorrect integer value: 'abc' for column 'edad' at row 1\")",
            "(1366, \"Incorrect integer value: '…' for column 'edad' at row 1\")",
            id="mariadb-valor",
        ),
        pytest.param(
            "(2627, b\"Violation of PRIMARY KEY constraint 'PK_c'. Cannot insert duplicate key in object 'dbo.c'. "
            'The duplicate key value is (1).DB-Lib error message 20018, severity 14:")',
            "(2627, b\"Violation of PRIMARY KEY constraint 'PK_c'. Cannot insert duplicate key in object 'dbo.c'. "
            'The duplicate key value is (…).DB-Lib error message 20018, severity 14:")',
            id="sqlserver-pymssql",
        ),
        pytest.param(
            "[23000] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]Cannot insert duplicate key row in object "
            "'dbo.c' with unique index 'ux'. The duplicate key value is (ana, 7). (2601) (SQLExecDirectW)",
            "[23000] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]Cannot insert duplicate key row in object "
            "'dbo.c' with unique index 'ux'. The duplicate key value is (…). (2601) (SQLExecDirectW)",
            id="sqlserver-pyodbc",
        ),
        pytest.param(
            "Conversion failed when converting the varchar value 'abc' to data type int.",
            "Conversion failed when converting the varchar value '…' to data type int.",
            id="sqlserver-conversion",
        ),
        pytest.param(
            "String or binary data would be truncated in table 'bd.dbo.c', column 'nombre'. Truncated value: 'Ana Se'.",
            "String or binary data would be truncated in table 'bd.dbo.c', column 'nombre'. Truncated value: '…'.",
            id="sqlserver-truncado",
        ),
        pytest.param(
            'duplicate key value violates unique constraint "clientes_pkey"\nDETAIL:  Key (id)=(1) already exists.',
            'duplicate key value violates unique constraint "clientes_pkey"',
            id="postgresql-detail",
        ),
        pytest.param(
            'invalid input syntax for type integer: "Ana Secreta"',
            'invalid input syntax for type integer: "…"',
            id="postgresql-sintaxis",
        ),
        pytest.param(
            "ORA-00001: unique constraint (BENCH.PK) violated on table BENCH.C columns (ID)\n"
            "ORA-03301: (ORA-00001 details) row with column values (ID:1) already exists",
            "ORA-00001: unique constraint (BENCH.PK) violated on table BENCH.C columns (ID)",
            id="oracle-03301",
        ),
    ],
)
def test_error_message_without_values(driver_message: str, expected: str) -> None:
    message = error_message(_wrapped(driver_message))

    assert message == f"(builtins.Exception) {expected}"
    assert "[SQL:" not in message and "parameters" not in message and "Secreta" not in message


def test_error_message_strings_and_urls() -> None:
    assert error_message("partición 2: fallo\n[SQL: INSERT …]\n[parameters: (1, 'x')]") == "partición 2: fallo"
    assert error_message("no conecta a postgresql+psycopg://u:clave@host/db") == "no conecta a [url]"
    assert error_message(RuntimeError()) == "RuntimeError"
    assert error_message("") == ""


def test_dump_error_msg_is_sanitized(tmp_path: Path) -> None:
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    for engine in (src, dst):
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE c (id INTEGER PRIMARY KEY, nombre TEXT)"))
    with src.begin() as conn:
        conn.execute(text("INSERT INTO c VALUES (1, 'Ana Secreta')"))
    with dst.begin() as conn:
        conn.execute(text("INSERT INTO c VALUES (1, 'otra')"))

    result = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, truncate_target=False)).run()

    (table,) = result.table_results
    assert table.status == "error"
    assert table.error_msg == "(sqlite3.IntegrityError) UNIQUE constraint failed: c.id"
