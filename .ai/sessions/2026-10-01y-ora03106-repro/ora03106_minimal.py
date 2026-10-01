"""Reproducción mínima de ORA-03106 con python-oracledb (modo thin), solo con el driver.

executemany de un UPDATE con batcherrors=True, un bind CLOB de más de ~8000 caracteres y una fila con error
(ORA-12899) → «ORA-03106: fatal two-task communication protocol error». Sin batcherrors, o con CLOB de 4001
caracteres, o con INSERT, funciona.

Uso: ORACLE_DSN=host:puerto/servicio ORACLE_USER=... ORACLE_PASSWORD=... python ora03106_minimal.py
(en util_bbdd la URL del banco se convierte con ``--from-sqlalchemy-url``; la contraseña no se imprime).
"""

from __future__ import annotations

import os
import sys

from urllib.parse import parse_qs, unquote, urlsplit

import oracledb


def _credentials() -> tuple[str, str, str]:
    if "--from-sqlalchemy-url" in sys.argv:
        url = urlsplit(os.environ["UTIL_BBDD_TEST_ORACLE_URL"].replace("oracle+oracledb://", "oracle://", 1))
        service = parse_qs(url.query).get("service_name", [""])[0]
        return unquote(url.username or ""), unquote(url.password or ""), f"{url.hostname}:{url.port}/{service}"
    return os.environ["ORACLE_USER"], os.environ["ORACLE_PASSWORD"], os.environ["ORACLE_DSN"]


def run(lob_chars: int, *, bad_row: bool, batcherrors: bool, clob_bind: bool, operation: str = "UPDATE") -> str:
    user, password, dsn = _credentials()
    connection = oracledb.connect(user=user, password=password, dsn=dsn)
    cursor = connection.cursor()
    try:
        cursor.execute("BEGIN EXECUTE IMMEDIATE 'DROP TABLE ora03106_repro'; EXCEPTION WHEN OTHERS THEN NULL; END;")
        cursor.execute("CREATE TABLE ora03106_repro (id NUMBER PRIMARY KEY, s VARCHAR2(10), c CLOB)")
        cursor.executemany("INSERT INTO ora03106_repro VALUES (:1, :2, :3)", [(i, "v", "x") for i in range(10)])
        connection.commit()
        if clob_bind:  # el valor largo como CLOB; si no, como cadena (el driver decide el tipo por la longitud)
            cursor.setinputsizes(None, oracledb.DB_TYPE_CLOB, None)
        rows = [("u", "y" * lob_chars, i) for i in range(10)]
        if bad_row:
            rows[4] = ("too long value", "y" * lob_chars, 4)  # ORA-12899 en s
        sql = "UPDATE ora03106_repro SET s = :1, c = :2 WHERE id = :3"
        if operation == "INSERT":
            rows = [(s_value, c_value, i + 100) for s_value, c_value, i in rows]
            sql = "INSERT INTO ora03106_repro (s, c, id) VALUES (:1, :2, :3)"
        try:
            cursor.executemany(sql, rows, batcherrors=batcherrors)
            errors = [error.full_code for error in cursor.getbatcherrors()] if batcherrors else []
            result = f"ok, batch errors: {errors}"
        except oracledb.Error as exc:
            result = f"raised {str(exc).splitlines()[0]}"
        connection.rollback()
        cursor.execute("DROP TABLE ora03106_repro")
        return result
    finally:
        connection.close()


if __name__ == "__main__":
    print(f"python-oracledb {oracledb.__version__}, thin={oracledb.is_thin_mode()}, Python {sys.version.split()[0]}")
    for operation in ("UPDATE", "INSERT"):
        for clob_bind in (True, False):
            for lob_chars in (4001, 8000, 9000, 40000):
                for batcherrors in (False, True):
                    outcome = run(
                        lob_chars, bad_row=True, batcherrors=batcherrors, clob_bind=clob_bind, operation=operation
                    )
                    bind = "DB_TYPE_CLOB" if clob_bind else "str"
                    print(
                        f"{operation}, bind {bind}, {lob_chars} chars, 1 bad row, batcherrors={batcherrors}: {outcome}",
                        flush=True,
                    )
