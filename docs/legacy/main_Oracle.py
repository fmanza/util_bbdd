#!/usr/bin/env python3
# main_Oracle.py
# Requiere: sqlalchemy, pandas, cx_Oracle (driver Oracle para SQLAlchemy)

"""_summary_
Notas importantes y recomendaciones

Ajusta DB1_URL, DB2_URL, SCHEMA1 y SCHEMA2 antes de ejecutar. Los esquemas deben ser mayúsculas (Oracle usa mayúsculas por defecto en el diccionario).

DBMS_METADATA.GET_DDL devuelve LOBs en algunos drivers; el script detecta .read() si es necesario.

Revisa manualmente los scripts generados antes de ejecutarlos en producción. Haz siempre backup y prueba en staging.
"""

import logging
import re

from pathlib import Path

import oracledb
import pandas as pd

from sqlalchemy import create_engine, inspect, text

# -------------------------------
# CONFIGURACIÓN
# -------------------------------
oracledb.init_oracle_client(r"C:\Desarrollo\driver\oracle\instantclient_11_2")

DB1_URL = "oracle+oracledb://COREUFV:COREUFV@10.20.0.236:1521/?service_name=DBTESTBIT"
DB2_URL = "oracle+oracledb://COREUFV:COREUFV@10.20.0.237:1521/?service_name=DBTESTBIT"

OUTPUT_EXCEL = Path("salida/diferencias_oracle.xlsx")
OUTPUT_LOG = Path("salida/auditoria_comparacion_oracle.log")

SCHEMA1 = "SEGISS_EXTREMADURA_FINAL"  # Cambia al esquema correcto
SCHEMA2 = "SIUSS_CM"  # Cambia al esquema correcto

# -------------------------------
# LOGGING (UTF-8)
# -------------------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Eliminar handlers previos (importante si se reejecuta en un notebook o intérprete)
if logger.hasHandlers():
    logger.handlers.clear()

file_handler = logging.FileHandler(OUTPUT_LOG, mode="w", encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


# -------------------------------
# NORMALIZADORES (para vistas y procs)
# -------------------------------
def normalize_ddl(def_sql: str) -> str:
    """Normaliza definiciones (vista/procedure) eliminando diferencias irrelevantes."""
    if not def_sql:
        return ""
    def_sql = re.sub(r"CREATE OR REPLACE FORCE", "CREATE OR REPLACE", def_sql, flags=re.IGNORECASE)
    def_sql = re.sub(r"\s+", " ", def_sql).strip().lower()
    return def_sql


# -------------------------------
# FUNCIONES AUXILIARES
# -------------------------------
def get_schema_info(inspector, schema):
    schema_info = []
    for table in inspector.get_table_names(schema=schema):
        columns = inspector.get_columns(table, schema=schema)
        pks = inspector.get_pk_constraint(table, schema=schema).get("constrained_columns", [])
        for col in columns:
            schema_info.append(
                {
                    "tabla": table,
                    "columna": col["name"],
                    "tipo": str(col["type"]),
                    "nullable": col["nullable"],
                    "primary_key": col["name"] in pks,
                }
            )
    return pd.DataFrame(schema_info)


def get_indices(insp, schema):
    rows = []
    for table in insp.get_table_names(schema=schema):
        try:
            for idx in insp.get_indexes(table, schema=schema):
                col_names = idx.get("column_names") or []
                col_names = [c for c in col_names if c is not None]
                col_str = ",".join(col_names) if col_names else "FUNCIONAL/EXPR"
                rows.append(
                    {
                        "tabla": table,
                        "nombre_indice": idx["name"],
                        "columnas": col_str,
                        "unico": idx.get("unique", False),
                    }
                )
        except NotImplementedError:
            pass
    return pd.DataFrame(rows)


def get_foreign_keys(inspector, schema):
    fks_info = []
    for table in inspector.get_table_names(schema=schema):
        fks = inspector.get_foreign_keys(table, schema=schema)
        for fk in fks:
            fks_info.append(
                {
                    "tabla": table,
                    "fk_nombre": fk.get("name"),
                    "columnas": ",".join(fk["constrained_columns"]),
                    "ref_tabla": fk["referred_table"],
                    "ref_columnas": ",".join(fk["referred_columns"]),
                }
            )
    return pd.DataFrame(fks_info)


# -------------------------------
# FUNCIONES PARA COMENTARIOS
# -------------------------------
def get_table_comments(engine, schema):
    q = text("SELECT table_name AS tabla, comments AS comentario FROM all_tab_comments WHERE owner=:schema")
    with engine.connect() as conn:
        rows = conn.execute(q, {"schema": schema.upper()}).mappings().all()
    return pd.DataFrame(rows)


def get_column_comments(engine, schema):
    q = text(
        "SELECT table_name AS tabla, column_name AS columna, comments AS comentario FROM all_col_comments WHERE owner=:schema"
    )
    with engine.connect() as conn:
        rows = conn.execute(q, {"schema": schema.upper()}).mappings().all()
    return pd.DataFrame(rows)


# -------------------------------
# FUNCIONES PARA VISTAS Y PROCS
# -------------------------------
def get_views(engine, schema):
    """
    Devuelve un DataFrame con las vistas y su definición SQL en la base de datos.
    """
    query = text("SELECT view_name FROM all_views WHERE owner=:schema")
    with engine.connect() as conn:
        vistas = [r[0] for r in conn.execute(query, {"schema": schema.upper()}).fetchall()]
    views_info = []
    for v in vistas:
        query = text("SELECT DBMS_METADATA.GET_DDL('VIEW', :vista, :schema) AS ddl FROM dual")
        with engine.connect() as conn:
            res = conn.execute(query, {"vista": v, "schema": schema.upper()}).first()
        ddl = res[0].read() if hasattr(res[0], "read") else res[0]
        views_info.append({"vista": v, "definicion": ddl, "def_normalizada": normalize_ddl(ddl)})
    return pd.DataFrame(views_info)


def get_procedures(engine, schema):
    query = text("SELECT object_name FROM all_procedures WHERE owner=:schema AND object_type='PROCEDURE'")
    with engine.connect() as conn:
        procs = [r[0] for r in conn.execute(query, {"schema": schema.upper()}).fetchall()]
    procs_info = []
    for p in procs:
        query = text("SELECT DBMS_METADATA.GET_DDL('PROCEDURE', :proc, :schema) AS ddl FROM dual")
        with engine.connect() as conn:
            res = conn.execute(query, {"proc": p, "schema": schema.upper()}).first()
        ddl = res[0].read() if hasattr(res[0], "read") else res[0]
        procs_info.append({"procedure": p, "definicion": ddl, "def_normalizada": normalize_ddl(ddl)})
    return pd.DataFrame(procs_info)


# -------------------------------
# GENERADORES SQL CRÍTICOS
# -------------------------------
def generar_sql_critico(
    origen_df,
    destino_df,
    df_tab_comments,
    df_col_comments,
    idx_origen,
    idx_destino,
    fk_origen,
    fk_destino,
    origen_name,
    destino_name,
    filename,
    engine=None,
):
    sql_lines = []
    tablas_origen = set(origen_df["tabla"].unique())
    tablas_destino = set(destino_df["tabla"].unique())

    # Tablas faltantes
    for tabla in sorted(tablas_origen - tablas_destino):
        cols = origen_df[origen_df["tabla"] == tabla]
        col_defs = []
        pk_cols = []
        for _, col in cols.iterrows():
            tipo = col["tipo"]
            nullable = "" if not col["nullable"] else "NULL"
            col_defs.append(f"{col['columna']} {tipo} {nullable}")
            if col["primary_key"]:
                pk_cols.append(col["columna"])
        create_sql = f"CREATE TABLE {tabla} (\n  " + ",\n  ".join(col_defs)
        if pk_cols:
            create_sql += ",\n  CONSTRAINT pk_" + tabla + " PRIMARY KEY (" + ", ".join(pk_cols) + ")"
        create_sql += "\n);\n"
        sql_lines.append(create_sql)

    # Columnas nuevas o modificadas
    tablas_comunes = tablas_origen.intersection(tablas_destino)
    for tabla in sorted(tablas_comunes):
        cols_origen = origen_df[origen_df["tabla"] == tabla].set_index("columna")
        cols_destino = destino_df[destino_df["tabla"] == tabla].set_index("columna")

        # ADD COLUMN
        for col in sorted(cols_origen.index.difference(cols_destino.index)):
            row = cols_origen.loc[col]
            tipo = row["tipo"]
            nullable = "" if not row["nullable"] else "NULL"
            sql_lines.append(f"ALTER TABLE {tabla} ADD ({col} {tipo} {nullable});")

        # MODIFY COLUMN
        for col in sorted(cols_origen.index.intersection(cols_destino.index)):
            r1 = cols_origen.loc[col]
            r2 = cols_destino.loc[col]
            if r1["tipo"] != r2["tipo"] or r1["nullable"] != r2["nullable"]:
                tipo = r1["tipo"]
                nullable = "" if not r1["nullable"] else "NULL"
                sql_lines.append(f"ALTER TABLE {tabla} MODIFY ({col} {tipo} {nullable});")

    # Comentarios (tabla y columnas)
    # df_tab_comments expects columns comentario_<origen_name> when passed earlier; but in generator we pass the df of origin comments already.
    for _, row in df_tab_comments.iterrows():
        comentario = (row[f"comentario_{origen_name}"] or "").replace("'", "''")
        sql_lines.append(f"COMMENT ON TABLE {row['tabla']} IS '{comentario}';")

    for _, row in df_col_comments.iterrows():
        comentario = (row[f"comentario_{origen_name}"] or "").replace("'", "''")
        sql_lines.append(f"COMMENT ON COLUMN {row['tabla']}.{row['columna']} IS '{comentario}';")

    # Índices
    for _, idx in idx_origen.iterrows():
        match = idx_destino[
            (idx_destino["tabla"] == idx["tabla"]) & (idx_destino["nombre_indice"] == idx["nombre_indice"])
        ]

        if idx["columnas"] == "FUNCIONAL/EXPR":
            if engine:  # intentar sacar el DDL
                try:
                    q = text("SELECT DBMS_METADATA.GET_DDL('INDEX', :idx, :schema) FROM dual")
                    with engine.connect() as conn:
                        res = conn.execute(q, {"idx": idx["nombre_indice"], "schema": origen_name.upper()}).first()
                    ddl = res[0].read() if hasattr(res[0], "read") else res[0]
                    sql_lines.append(ddl.strip() + ";")
                except Exception as e:
                    sql_lines.append(
                        f"-- Índice funcional {idx['nombre_indice']} en {idx['tabla']} → error al obtener DDL: {e}"
                    )
            else:
                sql_lines.append(f"-- Índice funcional {idx['nombre_indice']} en {idx['tabla']} → revisar manualmente")
            continue

        if match.empty:
            sql_lines.append(f"CREATE INDEX {idx['nombre_indice']} ON {idx['tabla']} ({idx['columnas']});")
        else:
            if (match.iloc[0]["columnas"] != idx["columnas"]) or (match.iloc[0]["unico"] != idx["unico"]):
                sql_lines.append(f"DROP INDEX {idx['nombre_indice']};")
                sql_lines.append(f"CREATE INDEX {idx['nombre_indice']} ON {idx['tabla']} ({idx['columnas']});")

    # Foreign Keys
    for _, fk in fk_origen.iterrows():
        match = fk_destino[(fk_destino["tabla"] == fk["tabla"]) & (fk_destino["fk_nombre"] == fk["fk_nombre"])]
        if (
            match.empty
            or (match.iloc[0]["columnas"] != fk["columnas"])
            or (match.iloc[0]["ref_tabla"] != fk["ref_tabla"])
            or (match.iloc[0]["ref_columnas"] != fk["ref_columnas"])
        ):
            if engine:
                try:
                    q = text("SELECT DBMS_METADATA.GET_DDL('CONSTRAINT', :cons, :schema) FROM dual")
                    with engine.connect() as conn:
                        res = conn.execute(q, {"cons": fk["fk_nombre"], "schema": origen_name.upper()}).first()
                    ddl = res[0].read() if hasattr(res[0], "read") else res[0]
                    sql_lines.append(ddl.strip() + ";")
                except Exception as e:
                    sql_lines.append(f"-- Constraint {fk['fk_nombre']} en {fk['tabla']} → error al obtener DDL: {e}")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"-- Script crítico Oracle\n-- Fuente: {origen_name} -> Destino: {destino_name}\n\n")
        f.write("\n".join(sql_lines))
    logging.info(f"💾 Script SQL crítico Oracle generado: {filename}")


def generar_script_sql(
    origen_df,
    destino_df,
    df_tab_comments,
    df_col_comments,
    idx_origen,
    idx_destino,
    fk_origen,
    fk_destino,
    origen_name,
    destino_name,
    filename,
):
    sql_lines = []
    tablas_origen = set(origen_df["tabla"].unique())
    tablas_destino = set(destino_df["tabla"].unique())
    # ---- Tablas faltantes (solo CREATE TABLE si no existe) ----
    for tabla in tablas_origen - tablas_destino:
        cols = origen_df[origen_df["tabla"] == tabla]
        col_defs = []
        pk_cols = []
        for _, col in cols.iterrows():
            tipo = col["tipo"]
            nullable = "NULL" if col["nullable"] else "NOT NULL"
            comentario_col = df_col_comments[
                (df_col_comments["tabla"] == tabla) & (df_col_comments["columna"] == col["columna"])
            ]
            comment_text = ""
            if not comentario_col.empty:
                comment_text = comentario_col.iloc[0][f"comentario_{origen_name}"] or ""
            col_defs.append(f"`{col['columna']}` {tipo} {nullable} COMMENT '{comment_text}'")
            if col["primary_key"]:
                pk_cols.append(f"`{col['columna']}`")
        create_sql = f"CREATE TABLE `{tabla}` (\n  " + ",\n  ".join(col_defs)
        if pk_cols:
            create_sql += ",\n  PRIMARY KEY (" + ", ".join(pk_cols) + ")"
        create_sql += "\n)"
        comentario_tabla = df_tab_comments[df_tab_comments["tabla"] == tabla]
        comment_text = ""
        if not comentario_tabla.empty:
            comment_text = comentario_tabla.iloc[0][f"comentario_{origen_name}"] or ""
        create_sql += f" COMMENT = '{comment_text}';"
        sql_lines.append(create_sql)
        # Índices y FKs para tabla nueva
        for _, idx in idx_origen[idx_origen["tabla"] == tabla].iterrows():
            idx_name = idx["nombre_indice"]
            columnas = idx["columnas"]
            unico = "UNIQUE " if idx["unico"] else ""
            sql_lines.append(f"CREATE {unico}INDEX `{idx_name}` ON `{tabla}` ({columnas});")
        for _, fk in fk_origen[fk_origen["tabla"] == tabla].iterrows():
            fk_name = fk["fk_nombre"]
            cols = fk["columnas"]
            ref_tabla = fk["ref_tabla"]
            ref_cols = fk["ref_columnas"]
            sql_lines.append(
                f"ALTER TABLE `{tabla}` ADD CONSTRAINT `{fk_name}` FOREIGN KEY ({cols}) REFERENCES `{ref_tabla}` ({ref_cols});"
            )
    # ---- Tablas existentes: solo ALTER TABLE para cambios ----
    tablas_comunes = tablas_origen.intersection(tablas_destino)
    for tabla in tablas_comunes:
        cols_origen = origen_df[origen_df["tabla"] == tabla].set_index("columna")
        cols_destino = destino_df[destino_df["tabla"] == tabla].set_index("columna")
        # ADD COLUMN
        for col in cols_origen.index.difference(cols_destino.index):
            col_info = cols_origen.loc[col]
            tipo = col_info["tipo"]
            nullable = "NULL" if col_info["nullable"] else "NOT NULL"
            pk = " PRIMARY KEY" if col_info["primary_key"] else ""
            comentario_col = df_col_comments[(df_col_comments["tabla"] == tabla) & (df_col_comments["columna"] == col)]
            comment_text = ""
            if not comentario_col.empty:
                comment_text = comentario_col.iloc[0][f"comentario_{origen_name}"] or ""
            sql_lines.append(
                f"ALTER TABLE `{tabla}` ADD COLUMN `{col}` {tipo} {nullable}{pk} COMMENT '{comment_text}';"
            )
        # DROP COLUMN
        for col in cols_destino.index.difference(cols_origen.index):
            sql_lines.append(f"ALTER TABLE `{tabla}` DROP COLUMN `{col}`;")
        # MODIFY COLUMN si tipo, nullable o pk cambia
        for col in cols_origen.index.intersection(cols_destino.index):
            row1 = cols_origen.loc[col]
            row2 = cols_destino.loc[col]
            if (
                (row1["tipo"] != row2["tipo"])
                or (row1["nullable"] != row2["nullable"])
                or (row1["primary_key"] != row2["primary_key"])
            ):
                tipo = row1["tipo"]
                nullable = "NULL" if row1["nullable"] else "NOT NULL"
                pk = " PRIMARY KEY" if row1["primary_key"] else ""
                comentario_col = df_col_comments[
                    (df_col_comments["tabla"] == tabla) & (df_col_comments["columna"] == col)
                ]
                comment_text = ""
                if not comentario_col.empty:
                    comment_text = comentario_col.iloc[0][f"comentario_{origen_name}"] or ""
                sql_lines.append(
                    f"ALTER TABLE `{tabla}` MODIFY COLUMN `{col}` {tipo} {nullable}{pk} COMMENT '{comment_text}';"
                )

    # ---- Comentarios de tablas ----
    for _, row in df_tab_comments.iterrows():
        comentario = (row.get("comentario") or "").replace("'", "''")
        sql_lines.append(f"COMMENT ON TABLE {row['tabla']} IS '{comentario}';")

    for _, row in df_col_comments.iterrows():
        comentario = (row.get("comentario") or "").replace("'", "''")
        sql_lines.append(f"COMMENT ON COLUMN {row['tabla']}.{row['columna']} IS '{comentario}';")

    # ---- Índices ----
    for _, row in idx_origen.iterrows():
        tabla = row["tabla"]
        idx_name = row["nombre_indice"]
        columnas = row["columnas"]
        unico = "UNIQUE " if row["unico"] else ""
        match = idx_destino[(idx_destino["tabla"] == tabla) & (idx_destino["nombre_indice"] == idx_name)]
        if match.empty:
            sql_lines.append(f"CREATE {unico}INDEX `{idx_name}` ON `{tabla}` ({columnas});")
        elif (match.iloc[0]["columnas"] != columnas) or (match.iloc[0]["unico"] != row["unico"]):
            sql_lines.append(f"DROP INDEX `{idx_name}` ON `{tabla}`;")
            sql_lines.append(f"CREATE {unico}INDEX `{idx_name}` ON `{tabla}` ({columnas});")

    # ---- Foreign Keys ----
    for _, row in fk_origen.iterrows():
        tabla = row["tabla"]
        fk_name = row["fk_nombre"]
        cols = row["columnas"]
        ref_tabla = row["ref_tabla"]
        ref_cols = row["ref_columnas"]
        match = fk_destino[(fk_destino["tabla"] == tabla) & (fk_destino["fk_nombre"] == fk_name)]
        if match.empty:
            sql_lines.append(
                f"ALTER TABLE `{tabla}` ADD CONSTRAINT `{fk_name}` FOREIGN KEY ({cols}) REFERENCES `{ref_tabla}` ({ref_cols});"
            )
        elif (
            (match.iloc[0]["columnas"] != cols)
            or (match.iloc[0]["ref_tabla"] != ref_tabla)
            or (match.iloc[0]["ref_columnas"] != ref_cols)
        ):
            sql_lines.append(f"ALTER TABLE `{tabla}` DROP FOREIGN KEY `{fk_name}`;")
            sql_lines.append(
                f"ALTER TABLE `{tabla}` ADD CONSTRAINT `{fk_name}` FOREIGN KEY ({cols}) REFERENCES `{ref_tabla}` ({ref_cols});"
            )
    # Guardar en fichero
    with open(filename, "w", encoding="utf-8") as f:
        f.write("-- Script optimizado generado automáticamente\n")
        f.write(f"-- Fuente: {origen_name} -> Destino: {destino_name}\n\n")
        for line in sql_lines:
            f.write(line + "\n")
    logging.info(f"💾 Script SQL optimizado generado: {filename}")


def generar_sql_views_critico(df_views_diff, origen_name, destino_name, filename):
    sql_lines = []
    for _, row in df_views_diff.iterrows():
        defin = row.get("definicion_db1")
        if defin:
            sql_lines.append(defin.strip() + ";")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"-- Script crítico VISTAS Oracle\n-- {origen_name} -> {destino_name}\n\n")
        f.write("\n".join(sql_lines))
    logging.info(f"💾 Script SQL crítico Vistas Oracle generado: {filename}")


def generar_sql_procs_critico(df_procs_diff, origen_name, destino_name, filename):
    sql_lines = []
    for _, row in df_procs_diff.iterrows():
        defin = row.get("definicion_db1")
        if defin:
            sql_lines.append(defin.strip() + ";")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"-- Script crítico PROCEDURES Oracle\n-- {origen_name} -> {destino_name}\n\n")
        f.write("\n".join(sql_lines))
    logging.info(f"💾 Script SQL crítico Procedures Oracle generado: {filename}")


def obtener_version_bbdd(engine):
    with engine.connect() as connection:
        result = connection.execute(text("SELECT banner FROM v$version WHERE banner LIKE 'Oracle Database%'"))
        db_version = result.scalar()  # Obtiene el primer valor de la primera fila
    return db_version


def main():
    # -------------------------------
    # CONEXIONES
    # -------------------------------
    logging.info(f"Conectando: {DB1_URL}")
    engine1 = create_engine(DB1_URL)
    logging.info(f"Conectando: {DB2_URL}")
    engine2 = create_engine(DB2_URL)

    logging.info(f"Inpección: {DB1_URL}")
    insp1 = inspect(engine1)
    logging.info(f"Inpección: {DB2_URL}")
    insp2 = inspect(engine2)

    db1_name = f"{engine1.url.host} - {engine1.url.username}"
    db2_name = f"{engine2.url.host} - {engine2.url.username}"

    logging.info(f"🔍 Inicio de la comparación entre {db1_name} y {db2_name}")

    # -------------------------------
    # EXTRAER INFO DE AMBAS DB
    # -------------------------------
    df1 = get_schema_info(insp1, SCHEMA1)
    df2 = get_schema_info(insp2, SCHEMA2)

    idx1 = get_indices(insp1, SCHEMA1)
    idx2 = get_indices(insp2, SCHEMA2)

    fk1 = get_foreign_keys(insp1, SCHEMA1)
    fk2 = get_foreign_keys(insp2, SCHEMA2)

    tbl_comments1 = get_table_comments(engine1, SCHEMA1)
    tbl_comments2 = get_table_comments(engine2, SCHEMA2)

    col_comments1 = get_column_comments(engine1, SCHEMA1)
    col_comments2 = get_column_comments(engine2, SCHEMA2)

    df_views_db1 = get_views(engine1, SCHEMA1)
    df_views_db2 = get_views(engine2, SCHEMA2)

    df_procs_db1 = get_procedures(engine1, SCHEMA1)
    df_procs_db2 = get_procedures(engine2, SCHEMA2)

    #
    db1_version = obtener_version_bbdd(engine1)
    db2_version = obtener_version_bbdd(engine2)
    logging.info(f"Versión de de BBDDD de {db1_name}: {db1_version}")
    logging.info(f"Versión de de BBDDD de {db2_name}: {db2_version}")

    # -------------------------------
    # COMPARACIONES
    # -------------------------------
    # Comparaciones tablas
    df_tablas = pd.DataFrame({"tabla": sorted(set(df1["tabla"]).union(set(df2["tabla"])))})
    df_tablas[f"existe_{SCHEMA1}"] = df_tablas["tabla"].isin(df1["tabla"].unique())
    df_tablas[f"existe_{SCHEMA2}"] = df_tablas["tabla"].isin(df2["tabla"].unique())

    # Tablas que están en SCHEMA1 pero no en SCHEMA2
    faltan_en_schema2 = df_tablas[(df_tablas[f"existe_{SCHEMA1}"]) & (~df_tablas[f"existe_{SCHEMA2}"])][
        ["tabla"]
    ].copy()
    faltan_en_schema2["falta_en"] = f"{SCHEMA2}"

    # Tablas que están en SCHEMA2 pero no en SCHEMA1
    faltan_en_schema1 = df_tablas[(df_tablas[f"existe_{SCHEMA2}"]) & (~df_tablas[f"existe_{SCHEMA1}"])][
        ["tabla"]
    ].copy()
    faltan_en_schema1["falta_en"] = f"{SCHEMA1}"

    # Unir ambos resultados
    df_tablas_faltantes = pd.concat([faltan_en_schema2, faltan_en_schema1], ignore_index=True)

    # Columnas: merge y diferencias
    df_columnas = pd.merge(df1, df2, on=["tabla", "columna"], how="outer", suffixes=(f"_{SCHEMA1}_1", f"_{SCHEMA2}_2"))
    # Rellenar NaN para comparaciones seguras
    df_columnas[f"tipo_{SCHEMA1}_1"] = df_columnas.get(f"tipo_{SCHEMA1}_1")
    df_columnas[f"tipo_{SCHEMA2}_2"] = df_columnas.get(f"tipo_{SCHEMA2}_2")
    # df_columnas = df_columnas.reset_index(drop=True)
    df_columnas_diff = df_columnas[
        (df_columnas.get(f"tipo_{SCHEMA1}_1") != df_columnas.get(f"tipo_{SCHEMA2}_2"))
        | (df_columnas.get(f"nullable_{SCHEMA1}_1") != df_columnas.get(f"nullable_{SCHEMA2}_2"))
        | (df_columnas.get(f"primary_key_{SCHEMA1}_1") != df_columnas.get(f"primary_key_{SCHEMA2}_2"))
    ]

    # Indices diff
    df_idx = pd.merge(
        idx1, idx2, on=["tabla", "nombre_indice"], how="outer", suffixes=(f"_{SCHEMA1}_1", f"_{SCHEMA2}_2")
    )
    df_idx_diff = df_idx[
        (df_idx.get(f"columnas_{SCHEMA1}_1") != df_idx.get(f"columnas_{SCHEMA2}_2"))
        | (df_idx.get(f"unico_{SCHEMA1}_1") != df_idx.get(f"unico_{SCHEMA2}_2"))
    ]

    # Foreign keys diff
    df_fk = pd.merge(fk1, fk2, on=["tabla", "fk_nombre"], how="outer", suffixes=(f"_{SCHEMA1}_1", f"_{SCHEMA2}_2"))
    df_fk_diff = df_fk[
        (df_fk.get(f"columnas_{SCHEMA1}_1") != df_fk.get(f"columnas_{SCHEMA2}_2"))
        | (df_fk.get(f"ref_tabla_{SCHEMA1}_1") != df_fk.get(f"ref_tabla_{SCHEMA2}_2"))
        | (df_fk.get(f"ref_columnas_{SCHEMA1}_1") != df_fk.get(f"ref_columnas_{SCHEMA2}_2"))
    ]

    # Comentarios diff
    df_tab_comments = pd.merge(
        tbl_comments1, tbl_comments2, on="tabla", how="outer", suffixes=(f"_{SCHEMA1}_1", f"_{SCHEMA2}_2")
    )
    df_tab_comments_diff = df_tab_comments[
        df_tab_comments.get(f"comentario_{SCHEMA1}_1") != df_tab_comments.get(f"comentario_{SCHEMA2}_2")
    ]
    df_tab_comments = df_tab_comments.fillna("")
    df_tab_comments_diff = df_tab_comments_diff.fillna("")

    df_col_comments = pd.merge(
        col_comments1, col_comments2, on=["tabla", "columna"], how="outer", suffixes=(f"_{SCHEMA1}_1", f"_{SCHEMA2}_2")
    )
    df_col_comments_diff = df_col_comments[
        df_col_comments.get(f"comentario_{SCHEMA1}_1") != df_col_comments.get(f"comentario_{SCHEMA2}_2")
    ]
    df_col_comments = df_col_comments.fillna("")
    df_col_comments_diff = df_col_comments_diff.fillna("")

    # Vistas y procedures diffs (normalizadas)
    df_views_diff: pd.DataFrame = pd.DataFrame()
    df_views_diff_reverse: pd.DataFrame = pd.DataFrame()
    if not df_views_db1.empty or not df_views_db2.empty:
        # Para DB1 -> DB2, invertir origen/destino
        df_views_diff = pd.merge(
            df_views_db1, df_views_db2, on="vista", how="outer", suffixes=(f"_{SCHEMA1}_1", f"_{SCHEMA2}_2")
        )
        df_views_diff[f"def_normalizada_{SCHEMA1}_1"] = df_views_diff.get(f"def_normalizada_{SCHEMA1}_1", "")
        df_views_diff[f"def_normalizada_{SCHEMA2}_2"] = df_views_diff.get(f"def_normalizada_{SCHEMA2}_2", "")
        df_views_diff = df_views_diff[
            df_views_diff[f"def_normalizada_{SCHEMA1}_1"] != df_views_diff[f"def_normalizada_{SCHEMA2}_2"]
        ]
        df_views_diff = df_views_diff.fillna("")

        # Para DB2 -> DB1, invertir origen/destino
        df_views_diff_reverse = df_views_diff.copy()
        df_views_diff_reverse[f"definicion_{f'{SCHEMA1}_1'}"], df_views_diff_reverse[f"definicion_{SCHEMA2}_2"] = (
            df_views_diff_reverse[f"definicion_{SCHEMA2}_2"],
            df_views_diff_reverse[f"definicion_{SCHEMA1}_1"],
        )

    df_procs_diff: pd.DataFrame = pd.DataFrame()
    if not df_procs_db1.empty or not df_procs_db2.empty:
        df_procs_diff = pd.merge(
            df_procs_db1, df_procs_db2, on="procedure", how="outer", suffixes=(f"_{SCHEMA1}_1", f"_{SCHEMA2}_2")
        )
        df_procs_diff[f"def_normalizada_{SCHEMA1}_1"] = df_procs_diff.get(f"def_normalizada_{SCHEMA1}_1", "")
        df_procs_diff[f"def_normalizada_{SCHEMA2}_2"] = df_procs_diff.get(f"def_normalizada_{SCHEMA2}_2", "")
        df_procs_diff = df_procs_diff[
            df_procs_diff[f"def_normalizada_{SCHEMA1}_1"] != df_procs_diff[f"def_normalizada_{SCHEMA2}_2"]
        ]
        df_procs_diff = df_procs_diff.fillna("")

    # -------------------------------
    # GUARDAR RESULTADOS
    # -------------------------------
    with pd.ExcelWriter(OUTPUT_EXCEL) as writer:
        df_tablas.to_excel(writer, sheet_name="tablas", index=False)
        df_tablas_faltantes.to_excel(writer, sheet_name="tablas_faltantes", index=False)
        df_columnas_diff.to_excel(writer, sheet_name="columnas_faltantes", index=False)
        df_idx_diff.to_excel(writer, sheet_name="indices_diferentes", index=False)
        df_fk_diff.to_excel(writer, sheet_name="foreign_keys_diferentes", index=False)
        df_tab_comments_diff.to_excel(writer, sheet_name="dif_comentarios_tablas", index=False)
        df_col_comments_diff.to_excel(writer, sheet_name="dif_comentarios_columnas", index=False)
        if not df_views_diff.empty:
            df_views_diff.to_excel(writer, sheet_name="vistas_diferentes", index=False)
        if not df_procs_diff.empty:
            df_procs_diff.to_excel(writer, sheet_name="procedures_diferentes", index=False)

    # -------------------------------
    # GENERAR SCRIPTS SQL EN AMBAS DIRECCIONES
    # -------------------------------
    OUTPUT_SQL_db1_db2 = Path(f"salida/sync_{SCHEMA1}_1_from_{SCHEMA2}_2.sql")
    OUTPUT_SQL_db2_db1 = Path(f"salida/sync_{SCHEMA2}_2_from_{SCHEMA1}_1.sql")
    generar_script_sql(
        df2,
        df1,
        df_tab_comments,
        df_col_comments,
        idx2,
        idx1,
        fk2,
        fk1,
        f"{SCHEMA2}_2",
        f"{SCHEMA1}_1",
        OUTPUT_SQL_db1_db2,
    )
    generar_script_sql(
        df1,
        df2,
        df_tab_comments,
        df_col_comments,
        idx1,
        idx2,
        fk1,
        fk2,
        f"{SCHEMA1}_1",
        f"{SCHEMA2}_2",
        OUTPUT_SQL_db2_db1,
    )

    OUTPUT_SQL_db1_db2_critico = Path(f"salida/sync_{SCHEMA1}_1_from_{SCHEMA2}_2_critico.sql")
    OUTPUT_SQL_db2_db1_critico = Path(f"salida/sync_{SCHEMA2}_2_from_{SCHEMA1}_1_critico.sql")
    generar_sql_critico(
        df2,
        df1,
        df_tab_comments,
        df_col_comments,
        idx2,
        idx1,
        fk2,
        fk1,
        f"{SCHEMA2}_2",
        f"{SCHEMA1}_1",
        OUTPUT_SQL_db1_db2_critico,
        engine2,
    )
    generar_sql_critico(
        df1,
        df2,
        df_tab_comments,
        df_col_comments,
        idx1,
        idx2,
        fk1,
        fk2,
        f"{SCHEMA1}_1",
        f"{SCHEMA2}_2",
        OUTPUT_SQL_db2_db1_critico,
        engine1,
    )

    ############## VISTAS #############
    if not df_views_db1.empty or not df_views_db2.empty:
        OUTPUT_SQL_db1_db2_critico_vistas = Path(f"salida/sync_{SCHEMA1}_1_from_{SCHEMA2}_2_vistas.sql")
        OUTPUT_SQL_db2_db1_critico_vistas = Path(f"salida/sync_{SCHEMA2}_2_from_{SCHEMA1}_1_vistas.sql")
        # Vistas: DB1 -> DB2
        generar_sql_views_critico(df_views_diff, f"{SCHEMA1}_1", f"{SCHEMA2}_2", OUTPUT_SQL_db2_db1_critico_vistas)
        # Para DB2 -> DB1, invertir origen/destino
        generar_sql_views_critico(
            df_views_diff_reverse, f"{SCHEMA2}_2", f"{SCHEMA1}_1", OUTPUT_SQL_db1_db2_critico_vistas
        )

    ############## PROCEDURES #############
    if not df_procs_db1.empty or not df_procs_db2.empty:
        OUTPUT_SQL_db1_db2_critico_proc = Path(f"salida/sync_{SCHEMA1}_1_from_{SCHEMA2}_2_proc.sql")
        OUTPUT_SQL_db2_db1_critico_proc = Path(f"salida/sync_{SCHEMA2}_2_from_{SCHEMA1}_1_proc.sql")

        # DB1 -> DB2
        generar_sql_procs_critico(df_procs_diff, db2_name, f"{SCHEMA1}_1", OUTPUT_SQL_db2_db1_critico_proc)
        # generar_sql_procs_critico(df_procs_diff.assign(definicion_db1=df_procs_diff.get(f"definicion_{db1_name}")), db1_name, db2_name, OUTPUT_SQL_db2_db1_critico_proc)

        # DB2 -> DB1
        df_procs_diff_reverse = df_procs_diff.copy()
        df_procs_diff_reverse[f"def_normalizada_{SCHEMA1}_1"], df_procs_diff_reverse[f"def_normalizada_{SCHEMA2}_2"] = (
            df_procs_diff_reverse[f"def_normalizada_{SCHEMA2}_2"],
            df_procs_diff_reverse[f"def_normalizada_{SCHEMA1}_1"],
        )
        df_procs_diff_reverse[f"definicion_{SCHEMA2}_2"], df_procs_diff_reverse[f"definicion_{SCHEMA2}_2"] = (
            df_procs_diff_reverse[f"definicion_{SCHEMA2}_2"],
            df_procs_diff_reverse[f"definicion_{SCHEMA1}_1"],
        )
        generar_sql_procs_critico(
            df_procs_diff_reverse, f"{SCHEMA1}_1", f"{SCHEMA1}_2", OUTPUT_SQL_db1_db2_critico_proc
        )

    # Procedures: scripts críticos
    # generar_sql_procs_critico(df_procs_diff.assign(definicion_db1=df_procs_diff.get("definicion_db1")), db1_name, db2_name, "critico_procs_db2_from_db1.sql")
    # DB2 -> DB1 (invertir)
    # df_procs_rev = df_procs_diff.copy()
    # df_procs_rev[f"definicion_{db1_name}"], df_procs_rev[f"definicion_{db2_name}"] = df_procs_rev.get(f"definicion_{db2_name}", ""), df_procs_rev.get(f"definicion_{db1_name}", "")
    # df_procs_rev[f"def_normalizada_{db1_name}"], df_procs_rev[f"def_normalizada_{db2_name}"] = (
    #    df_procs_rev[f"def_normalizada_{db2_name}"],
    #    df_procs_rev[f"def_normalizada_{db1_name}"],
    # )
    # generar_sql_procs_critico(df_procs_rev, db2_name, db1_name, OUTPUT_SQL_db1_db2_critico_proc)

    logging.info("✅ Comparación finalizada. Resultados guardados en Excel, SQL y log de auditoría.")
    print("✅ Comparación finalizada. Revisa el Excel, los scripts SQL y el log de auditoría.")


if __name__ == "__main__":
    main()
