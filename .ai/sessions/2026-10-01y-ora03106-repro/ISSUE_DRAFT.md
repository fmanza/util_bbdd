# Borrador de issue para python-oracledb (no publicado)

Destino: https://github.com/oracle/python-oracledb/issues — **lo publica el usuario** (acción externa; D-4 de
`../2026-10-01v-plan-pendientes-mariadb-connector/PLAN_AUDIT_PLAN.md`). Sin credenciales ni datos del banco.

---

**Title:** Thin mode: `executemany(..., batcherrors=True)` on an UPDATE with a large LOB bind and one failing row raises ORA-03106

**Describe the bug**

In thin mode, `cursor.executemany()` of an `UPDATE` with `batcherrors=True` raises
`ORA-03106: fatal two-task communication protocol error` when the batch binds a long string/CLOB value (more than
8000 characters) and one of the rows fails with a row-level error (here ORA-12899). The connection is unusable
afterwards. Expected: the good rows are updated and `cursor.getbatcherrors()` returns the ORA-12899 for the failing
row, which is what happens with shorter values, without `batcherrors` (ORA-12899 is raised normally) and with the same
data in an `INSERT`.

| Bind of the long value | Length | 4.0.1 | 4.0.2 | 26.0.1 |
|---|---|---|---|---|
| plain `str` (no `setinputsizes`) | 4001 / 8000 | ok | ok | ok |
| plain `str` | 9000 / 40000 | **ORA-03106** | **ORA-03106** | **ORA-03106** |
| `setinputsizes(..., oracledb.DB_TYPE_CLOB, ...)` | 4001 / 8000 | ok | ok | ok |
| `setinputsizes(..., oracledb.DB_TYPE_CLOB, ...)` | 9000 / 40000 | ok | ok | **ORA-03106** |
| same data, `INSERT` instead of `UPDATE` | any | ok | ok | ok |

All cases with `batcherrors=False` raise the expected ORA-12899.

**Environment**

- python-oracledb 4.0.1, 4.0.2 and 26.0.1, thin mode
- Python 3.14.2, Windows 11 (x64)
- Oracle AI Database 26ai Free Release 23.26.3.0.0 (container `gvenzl/oracle-free:23-slim-faststart`),
  NLS_CHARACTERSET AL32UTF8

**To reproduce**

```python
import oracledb

connection = oracledb.connect(user=..., password=..., dsn=...)
cursor = connection.cursor()
cursor.execute("CREATE TABLE ora03106_repro (id NUMBER PRIMARY KEY, s VARCHAR2(10), c CLOB)")
cursor.executemany("INSERT INTO ora03106_repro VALUES (:1, :2, :3)", [(i, "v", "x") for i in range(10)])
connection.commit()

rows = [("u", "y" * 9000, i) for i in range(10)]
rows[4] = ("too long value", "y" * 9000, 4)  # ORA-12899 on column s
cursor.executemany("UPDATE ora03106_repro SET s = :1, c = :2 WHERE id = :3", rows, batcherrors=True)
# -> oracledb.exceptions.DatabaseError: ORA-03106: fatal two-task communication protocol error
# expected: rows updated except id 4; cursor.getbatcherrors() -> [ORA-12899 at offset 4]
```

With `cursor.setinputsizes(None, oracledb.DB_TYPE_CLOB, None)` before the `executemany`, 4.0.x works and 26.0.1 fails.

---

Notas para util_bbdd (no forman parte del issue):
- Script completo: `ora03106_minimal.py` (matriz `ora03106_matrix.log`); se ejecutó con cada versión en un venv aparte.
- `BulkCrud(on_error="isolate")` ya evita el caso: en UPDATE con columnas LOB usa la bisección, no `batcherrors`
  (sesión `2026-10-01s`). El INSERT con `batcherrors` no falla en ninguna versión.
