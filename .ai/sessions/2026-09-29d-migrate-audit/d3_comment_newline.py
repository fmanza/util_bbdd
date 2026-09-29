"""Deuda D3: un comentario con salto de línea escrito como ``-- ...`` sale del comentario en el DDL (PG/SQL Server)."""

from util_bbdd.migrate.emitters.postgresql import PostgreSQLDDLEmitter
from util_bbdd.migrate.emitters.sqlserver import SQLServerDDLEmitter
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable

COMMENT = "Importe neto\nsegunda línea del comentario"
for emitter in (PostgreSQLDDLEmitter(), SQLServerDDLEmitter()):
    column = CanonicalColumn(
        name="importe", original_name="IMPORTE", oracle_type="NUMBER", target_type="NUMERIC(10,2)", nullable=True,
        default=None, comment=COMMENT, ordinal=1,
    )
    table = CanonicalTable("t", "T", "s", [column], [], [], [], "Tabla\nde prueba", [])
    [ddl] = emitter.emit_statements([table])
    print(f"== {type(emitter).__name__}")
    print(ddl)
