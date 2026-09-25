"""Reproducción P-30/C-1: SQL generado para columnas binarias, ejecutado en motores reales vía docker exec.

Uso: python binrepro.py <etiqueta>   (escribe <etiqueta>_<dialecto>.sql y ejecuta; imprime OK/FAIL por valor)
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys

from pathlib import Path

import pandas as pd

from sqlalchemy import Column, Integer, LargeBinary, MetaData, Table, create_engine, insert

from util_bbdd.bulk._support.sql_helpers import generate_insert_sql, generate_update_sql, restore_binary_values
from util_bbdd.bulk.normalize import dataframe_to_sql_records

HERE = Path(__file__).parent
TABLE = "zz_util_bbdd_hotfix_bin"
VALUES: list[bytes | None] = [
    b"abc",
    b"a'b",
    b"a\\b",
    b"\\x41",
    b"%(x)s %s ?",
    "ñ€".encode(),
    b"\x00\xff",
    bytes(range(256)),
    None,
]

DIALECTS = {
    "sqlite": ("sqlite://", None),
    "postgresql": ("postgresql+psycopg://", "util_bbdd_bench_postgres"),
    "mysql": ("mysql+pymysql://", "util_bbdd_bench_mysql"),
    "mariadb": ("mariadb+pymysql://", "util_bbdd_bench_mariadb"),
    "mssql": ("mssql+pymssql://", "util_bbdd_bench_mssql"),
    "oracle": ("oracle+oracledb://", "util_bbdd_bench_oracle"),
}

DDL = {
    "sqlite": f"DROP TABLE IF EXISTS {TABLE}; CREATE TABLE {TABLE} (id INTEGER PRIMARY KEY, bin BLOB);",
    "postgresql": f"DROP TABLE IF EXISTS {TABLE}; CREATE TABLE {TABLE} (id INTEGER PRIMARY KEY, bin BYTEA);",
    "mysql": f"DROP TABLE IF EXISTS {TABLE}; CREATE TABLE {TABLE} (id INTEGER PRIMARY KEY, bin LONGBLOB);",
    "mariadb": f"DROP TABLE IF EXISTS {TABLE}; CREATE TABLE {TABLE} (id INTEGER PRIMARY KEY, bin LONGBLOB);",
    "mssql": f"IF OBJECT_ID('{TABLE}') IS NOT NULL DROP TABLE {TABLE};\nCREATE TABLE {TABLE} (id INTEGER PRIMARY KEY, bin VARBINARY(MAX));",
    "oracle": (
        f"BEGIN EXECUTE IMMEDIATE 'DROP TABLE {TABLE}'; EXCEPTION WHEN OTHERS THEN NULL; END;\n/\n"
        f"CREATE TABLE {TABLE} (id INTEGER PRIMARY KEY, bin BLOB);"
    ),
}
SELECT = {
    "sqlite": f"SELECT id, hex(bin), typeof(bin) FROM {TABLE} ORDER BY id;",
    "postgresql": f"SELECT id, upper(encode(bin, 'hex')) FROM {TABLE} ORDER BY id;",
    "mysql": f"SELECT id, HEX(bin) FROM {TABLE} ORDER BY id;",
    "mariadb": f"SELECT id, HEX(bin) FROM {TABLE} ORDER BY id;",
    "mssql": f"SELECT id, CONVERT(VARCHAR(MAX), bin, 2) FROM {TABLE} ORDER BY id;",
    "oracle": f"SELECT id, RAWTOHEX(DBMS_LOB.SUBSTR(bin, 2000, 1)) FROM {TABLE} ORDER BY id;",
}
DROP = {
    "oracle": f"DROP TABLE {TABLE};",
    "mssql": f"DROP TABLE {TABLE};",
}
RUN = {
    "postgresql": 'psql -X -q -A -t -F "|" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/r.sql',
    "mysql": 'mysql -N -B --force -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" < /tmp/r.sql 2>&1 | grep -v "Using a password"',
    "mariadb": 'mariadb -N -B --force -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" "$MARIADB_DATABASE" < /tmp/r.sql',
    "mssql": '/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -d bench -y 0 -s "|" -i /tmp/r.sql',
    "oracle": (
        '/opt/oracle/product/26ai/dbhomeFree/bin/sqlplus -S "$APP_USER/$APP_USER_PASSWORD@localhost/FREEPDB1" @/tmp/r.sql'
    ),
}


def lines_for(dialect_name: str, op: str) -> list[str]:
    dialect = create_engine(DIALECTS[dialect_name][0]).dialect
    table = Table(TABLE, MetaData(), Column("id", Integer, primary_key=True), Column("bin", LargeBinary))
    df = pd.DataFrame({"id": range(1, len(VALUES) + 1), "bin": VALUES})
    records = dataframe_to_sql_records(df)
    restore_binary_values(records, table)  # como BulkCrud.__record_blocks
    if op == "insert":
        return generate_insert_sql(insert(table), records, dialect)
    for record in records:
        record["id_pk"] = record["id"]
    return generate_update_sql(
        table=table, records=records, update_cols=["bin"], pk_param_map={"id": "id_pk"}, pk_cols=["id"], dialect=dialect
    )


def script(name: str) -> str:
    """DDL + INSERT con NULL (para que exista la fila) + UPDATE generado + INSERT generado en otra tabla lógica."""
    ins = lines_for(name, "insert")
    parts = [DDL[name], *ins, SELECT[name]]
    if name == "oracle":
        parts = ["SET HEADING OFF FEEDBACK OFF PAGESIZE 0 LINESIZE 32767 LONG 100000 COLSEP '|'", *parts]
    parts.append(DROP.get(name, f"DROP TABLE {TABLE};"))
    if name == "oracle":
        parts.append("EXIT")
    return ("\nGO\n" if name == "mssql" else "\n").join(parts) + "\n"


def run(name: str, sql: str) -> str:
    if name == "sqlite":
        con = sqlite3.connect(":memory:")
        out = []
        for stmt in [s for s in sql.split(";\n") if s.strip()]:
            try:
                rows = con.execute(stmt).fetchall() if stmt.lstrip().upper().startswith("SELECT") else con.executescript(stmt + ";") and []
                out += ["|".join(str(c) for c in r) for r in rows]
            except sqlite3.Error as e:
                out.append(f"ERROR: {e}")
        return "\n".join(out)
    container = DIALECTS[name][1]
    proc = subprocess.run(
        ["docker", "exec", "-i", container, "sh", "-c", f"cat > /tmp/r.sql && {RUN[name]}"],
        input=sql.encode(),
        capture_output=True,
        check=False,
    )
    return (proc.stdout + proc.stderr).decode(errors="replace")


def check(name: str, output: str) -> list[str]:
    got: dict[int, str] = {}
    for line in output.splitlines():
        cells = [c.strip() for c in line.strip().replace("	", "|").split("|")]
        if len(cells) >= 2 and cells[0].isdigit():
            got[int(cells[0])] = "|".join(cells[1:])
    report = []
    for idx, value in enumerate(VALUES, start=1):
        want = "" if value is None else value.hex().upper()
        have = got.get(idx)
        shown = repr(value)[:14]
        if have is None:
            report.append(f"  {idx} {shown:<16} FAIL (fila no insertada)")
            continue
        hex_part, *extra = have.split("|")
        ok = hex_part in (want, "NULL" if value is None else want) and not (extra and extra[0] == "text")
        report.append(f"  {idx} {shown:<16} {'OK  ' if ok else 'FAIL'} {'' if ok else f'guardado={have[:40]!r}'}")
    errors = [line for line in output.splitlines() if "ERROR" in line.upper() or "ORA-" in line or "Msg " in line]
    return report + [f"  ! {e[:150]}" for e in errors[:4]]


if __name__ == "__main__":
    label = sys.argv[1]
    names = sys.argv[2].split(",") if len(sys.argv) > 2 else list(DIALECTS)
    for name in names:
        sql = script(name)
        (HERE / f"{label}_{name}.sql").write_text(sql, encoding="utf-8")
        output = run(name, sql)
        (HERE / f"{label}_{name}.out").write_text(output, encoding="utf-8")
        report = check(name, output)
        fails = sum("FAIL" in r for r in report)
        print(f"{name}: {len(VALUES) - fails}/{len(VALUES)} OK")
        print("\n".join(report))
