import logging
import re

from pathlib import Path

import pandas as pd

from sqlalchemy import create_engine, inspect, text
from util.medir_tiempo import medir_tiempo

# -------------------------------
# CONFIGURACIÓN
# -------------------------------
# DB1_URL = "mariadb+mariadbconnector://SOCYALPRO_DEMO:SOCYALPRO_DEMO@10.20.0.245:3306/SOCYALPRO_DEMO"
# DB2_URL = "mariadb+mariadbconnector://SOCYALPRO:SOCYALPRO@10.20.0.245:3306/SOCYALPRO"
DB1_URL = "mariadb+mariadbconnector://CABLANZAROTEDEMO:CABLANZAROTEDEMO@10.20.0.245:3306/CABLANZAROTEDEMO"
DB2_URL = "mariadb+mariadbconnector://SOCYALPRO:SOCYALPRO@10.20.0.245:3306/SOCYALPRO"

OUTPUT_EXCEL = Path("salida/diferencias_mariadb.xlsx")
OUTPUT_LOG = Path("salida/auditoria_comparacion.log")

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
# FUNCIONES AUXILIARES
# -------------------------------
def get_schema_info(inspector):
    schema_info = []
    for table in inspector.get_table_names():
        columns = inspector.get_columns(table)
        pks = inspector.get_pk_constraint(table).get("constrained_columns", [])
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


def get_indices(inspector):
    indices_info = []
    for table in inspector.get_table_names():
        try:
            indices = inspector.get_indexes(table)
            for idx in indices:
                indices_info.append(
                    {
                        "tabla": table,
                        "nombre_indice": idx["name"],
                        "columnas": ",".join(idx["column_names"]),
                        "unico": idx.get("unique", False),
                    }
                )
        except NotImplementedError:
            pass
    return pd.DataFrame(indices_info)


def get_foreign_keys(inspector):
    fks_info = []
    for table in inspector.get_table_names():
        fks = inspector.get_foreign_keys(table)
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


def get_table_comments(engine):
    query = text("SHOW TABLE STATUS")
    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.mappings().all()
    return pd.DataFrame([{"tabla": row["Name"], "comentario": row["Comment"]} for row in rows])


def get_column_comments(engine, inspector):
    column_comments = []
    for table in inspector.get_table_names():
        query = text(f"SHOW FULL COLUMNS FROM `{table}`")
        with engine.connect() as conn:
            result = conn.execute(query)
            rows = result.mappings().all()
        for row in rows:
            column_comments.append({"tabla": table, "columna": row["Field"], "comentario": row["Comment"]})
    return pd.DataFrame(column_comments)


def get_views(engine):
    """
    Devuelve un DataFrame con las vistas y su definición SQL en la base de datos.
    """
    query = text("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
    with engine.connect() as conn:
        result = conn.execute(query)
        vistas = [row[0] for row in result.fetchall()]

    views_info = []
    for vista in vistas:
        q = text(f"SHOW CREATE VIEW `{vista}`")
        with engine.connect() as conn:
            res = conn.execute(q).mappings().first()
        views_info.append(
            {
                "vista": vista,
                "definicion": res["Create View"],  # SQL completo de la vista
            }
        )
    return pd.DataFrame(views_info)


def normalize_view_definition(def_sql: str) -> str:
    """
    Normaliza la definición de una vista:
    - Elimina DEFINER
    - Elimina cualquier prefijo de base de datos en todo el SQL
    - Convierte a minúsculas
    """
    if not def_sql:
        return ""

    # 1. Eliminar DEFINER=`usuario`@`host`
    def_sql = re.sub(r"DEFINER=`[^`]+`@`[^`]+`", "", def_sql, flags=re.IGNORECASE)

    # 2. Eliminar cualquier prefijo de base de datos en todo el SQL
    #    Detecta: (`?dbname`?).(`?tabla`?) y lo reemplaza por `tabla`
    def_sql = re.sub(
        r"(`?)[a-zA-Z0-9_]+`?\.`([a-zA-Z0-9_]+)`?",
        r"`\2`",  # Mantiene el backtick solo en el nombre de tabla
        def_sql,
    )

    # 3. Normalizar espacios y pasar a minúsculas
    def_sql = re.sub(r"\s+", " ", def_sql).strip().lower()

    return def_sql


def get_procedures(engine, db_name):
    query = text(f"SHOW PROCEDURE STATUS WHERE Db='{db_name}'")
    with engine.connect() as conn:
        result = conn.execute(query).mappings().all()
    procs_info = []
    for row in result:
        proc_name = row["Name"]
        q = text(f"SHOW CREATE PROCEDURE `{proc_name}`")
        with engine.connect() as conn:
            res = conn.execute(q).mappings().first()
        procs_info.append(
            {
                "procedure": proc_name,
                "definicion": res["Create Procedure"],
                "def_normalizada": normalize_routine_definition(res["Create Procedure"]),
            }
        )

    # Reemplazar todos los None por comillas vacías
    df_procedures = pd.DataFrame(procs_info)
    df_procedures = df_procedures.fillna("")

    return df_procedures


def normalize_routine_definition(def_sql: str) -> str:
    """
    Normaliza la definición de un procedure/function:
    - Elimina DEFINER
    - Convierte a minúsculas
    - Quita espacios extra
    """
    if not def_sql:
        return ""
    def_sql = re.sub(r"DEFINER=`[^`]+`@`[^`]+`", "", def_sql, flags=re.IGNORECASE)
    def_sql = re.sub(r"\s+", " ", def_sql).strip().lower()
    return def_sql


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
        sql_lines.append(f"ALTER TABLE `{row['tabla']}` COMMENT = '{row[f'comentario_{origen_name}'] or ''}';")

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
):
    sql_lines = []
    tablas_origen = set(origen_df["tabla"].unique())
    tablas_destino = set(destino_df["tabla"].unique())

    # Tablas faltantes: CREATE TABLE completo
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
            comment_text = comentario_col.iloc[0][f"comentario_{origen_name}"] if not comentario_col.empty else ""
            col_defs.append(f"`{col['columna']}` {tipo} {nullable} COMMENT '{comment_text}'")
            if col["primary_key"]:
                pk_cols.append(f"`{col['columna']}`")
        create_sql = f"CREATE TABLE `{tabla}` (\n  " + ",\n  ".join(col_defs)
        if pk_cols:
            create_sql += ",\n  PRIMARY KEY (" + ", ".join(pk_cols) + ")"
        create_sql += "\n)"
        comentario_tabla = df_tab_comments[df_tab_comments["tabla"] == tabla]
        comment_text = comentario_tabla.iloc[0][f"comentario_{origen_name}"] if not comentario_tabla.empty else ""
        create_sql += f" COMMENT = '{comment_text}';"
        sql_lines.append(create_sql)

        # Índices
        for _, idx in idx_origen[idx_origen["tabla"] == tabla].iterrows():
            unico = "UNIQUE " if idx["unico"] else ""
            sql_lines.append(f"CREATE {unico}INDEX `{idx['nombre_indice']}` ON `{tabla}` ({idx['columnas']});")
        # Foreign keys
        for _, fk in fk_origen[fk_origen["tabla"] == tabla].iterrows():
            sql_lines.append(
                f"ALTER TABLE `{tabla}` ADD CONSTRAINT `{fk['fk_nombre']}` FOREIGN KEY ({fk['columnas']}) REFERENCES `{fk['ref_tabla']}` ({fk['ref_columnas']});"
            )

    # Tablas existentes: solo cambios críticos
    tablas_comunes = tablas_origen.intersection(tablas_destino)
    for tabla in tablas_comunes:
        cols_origen = origen_df[origen_df["tabla"] == tabla].set_index("columna")
        cols_destino = destino_df[destino_df["tabla"] == tabla].set_index("columna")

        # ADD COLUMN
        for col in cols_origen.index.difference(cols_destino.index):
            row = cols_origen.loc[col]
            nullable = "NULL" if row["nullable"] else "NOT NULL"
            pk = " PRIMARY KEY" if row["primary_key"] else ""
            comentario_col = df_col_comments[(df_col_comments["tabla"] == tabla) & (df_col_comments["columna"] == col)]
            comment_text = comentario_col.iloc[0][f"comentario_{origen_name}"] if not comentario_col.empty else ""
            sql_lines.append(
                f"ALTER TABLE `{tabla}` ADD COLUMN `{col}` {row['tipo']} {nullable}{pk} COMMENT '{comment_text}';"
            )

        # MODIFY COLUMN
        for col in cols_origen.index.intersection(cols_destino.index):
            r1 = cols_origen.loc[col]
            r2 = cols_destino.loc[col]
            if r1["tipo"] != r2["tipo"] or r1["nullable"] != r2["nullable"] or r1["primary_key"] != r2["primary_key"]:
                nullable = "NULL" if r1["nullable"] else "NOT NULL"
                pk = " PRIMARY KEY" if r1["primary_key"] else ""
                comentario_col = df_col_comments[
                    (df_col_comments["tabla"] == tabla) & (df_col_comments["columna"] == col)
                ]
                comment_text = comentario_col.iloc[0][f"comentario_{origen_name}"] if not comentario_col.empty else ""
                sql_lines.append(
                    f"ALTER TABLE `{tabla}` MODIFY COLUMN `{col}` {r1['tipo']} {nullable}{pk} COMMENT '{comment_text}';"
                )

    # Comentarios de tablas
    for _, row in df_tab_comments.iterrows():
        sql_lines.append(f"ALTER TABLE `{row['tabla']}` COMMENT = '{row[f'comentario_{origen_name}'] or ''}';")

    # Crear índices faltantes
    for _, row in idx_origen.iterrows():
        match = idx_destino[
            (idx_destino["tabla"] == row["tabla"]) & (idx_destino["nombre_indice"] == row["nombre_indice"])
        ]
        unico = "UNIQUE " if row["unico"] else ""
        if match.empty:
            sql_lines.append(f"CREATE {unico}INDEX `{row['nombre_indice']}` ON `{row['tabla']}` ({row['columnas']});")

    # Crear foreign keys faltantes
    for _, row in fk_origen.iterrows():
        match = fk_destino[(fk_destino["tabla"] == row["tabla"]) & (fk_destino["fk_nombre"] == row["fk_nombre"])]
        if match.empty:
            sql_lines.append(
                f"ALTER TABLE `{row['tabla']}` ADD CONSTRAINT `{row['fk_nombre']}` FOREIGN KEY ({row['columnas']}) REFERENCES `{row['ref_tabla']}` ({row['ref_columnas']});"
            )

    # Guardar SQL crítico
    with open(filename, "w", encoding="utf-8") as f:
        f.write("-- Script crítico generado automáticamente\n")
        f.write(f"-- Fuente: {origen_name} -> Destino: {destino_name}\n\n")
        for line in sql_lines:
            f.write(line + "\n")

    logging.info(f"💾 Script SQL crítico generado: {filename}")


def generar_sql_views_critico(df_views_diff, origen_name, destino_name, filename):
    sql_lines = []
    for _, row in df_views_diff.iterrows():
        if pd.notna(row[f"definicion_{origen_name}"]):
            # Drop + Create para asegurar sincronización de la vista
            sql_lines.append(f"DROP VIEW IF EXISTS `{row['vista']}`;")
            sql_lines.append(row[f"definicion_{origen_name}"] + ";")  # Definición de origen

    # Guardar SQL crítico
    with open(filename, "w", encoding="utf-8") as f:
        f.write("-- Script crítico para vistas generado automáticamente\n")
        f.write(f"-- Fuente: {origen_name} -> Destino: {destino_name}\n\n")
        for line in sql_lines:
            f.write(line + "\n")
    logging.info(f"💾 Script SQL crítico de vistas generado: {filename}")


def generar_sql_procs_critico(df_procs_diff, origen_name, destino_name, filename):
    sql_lines = []
    for _, row in df_procs_diff.iterrows():
        if pd.notna(row[f"def_normalizada_{origen_name}"]):
            sql_lines.append(f"DROP PROCEDURE IF EXISTS `{row['procedure']}`;")
            sql_lines.append(row[f"definicion_{origen_name}"] + ";")
    with open(filename, "w", encoding="utf-8") as f:
        f.write("-- Script crítico para procedures\n")
        f.write(f"-- Fuente: {origen_name} -> Destino: {destino_name}\n\n")
        for line in sql_lines:
            f.write(line + "\n")
    logging.info(f"💾 Script SQL crítico de procedures generado: {filename}")


def obtener_version_bbdd(engine):
    with engine.connect() as connection:
        result = connection.execute(text("SELECT VERSION();"))
        db_version = result.scalar()  # Obtiene el primer valor de la primera fila
    return db_version


@medir_tiempo("Comparación de BBDD")
def main():
    # -------------------------------
    # CONEXIONES
    # -------------------------------
    engine1 = create_engine(DB1_URL)
    engine2 = create_engine(DB2_URL)

    insp1 = inspect(engine1)
    insp2 = inspect(engine2)

    db1_name = engine1.url.database
    db2_name = engine2.url.database

    logging.info(f"🔍 Inicio de la comparación entre {db1_name} y {db2_name}")

    # -------------------------------
    # EXTRAER INFO DE AMBAS DB
    # -------------------------------
    df1 = get_schema_info(insp1)
    df2 = get_schema_info(insp2)

    idx1 = get_indices(insp1)
    idx2 = get_indices(insp2)

    fk1 = get_foreign_keys(insp1)
    fk2 = get_foreign_keys(insp2)

    tbl_comments1 = get_table_comments(engine1)
    tbl_comments2 = get_table_comments(engine2)

    col_comments1 = get_column_comments(engine1, insp1)
    col_comments2 = get_column_comments(engine2, insp2)

    df_views_db1 = get_views(engine1)
    df_views_db2 = get_views(engine2)

    df_procs_db1 = get_procedures(engine1, db1_name)
    df_procs_db2 = get_procedures(engine2, db2_name)

    #
    db1_version = obtener_version_bbdd(engine1)
    db2_version = obtener_version_bbdd(engine2)
    logging.info(f"Versión de de BBDDD de {db1_name}: {db1_version}")
    logging.info(f"Versión de de BBDDD de {db2_name}: {db2_version}")

    # -------------------------------
    # COMPARACIONES
    # -------------------------------
    # Tablas
    tablas_db1 = set(df1["tabla"].unique())
    tablas_db2 = set(df2["tabla"].unique())

    tablas_faltan_db1 = list(tablas_db2 - tablas_db1)
    tablas_faltan_db2 = list(tablas_db1 - tablas_db2)

    df_tablas_faltantes = pd.DataFrame(
        {
            "falta_en": [db1_name] * len(tablas_faltan_db1) + [db2_name] * len(tablas_faltan_db2),
            "tabla": tablas_faltan_db1 + tablas_faltan_db2,
        }
    )
    logging.info(f"Tablas faltantes: {len(df_tablas_faltantes)}")

    # Columnas
    columnas_faltantes = []
    diferencias_columnas = []

    for tabla in tablas_db1.intersection(tablas_db2):
        cols_db1 = df1[df1["tabla"] == tabla].set_index("columna")
        cols_db2 = df2[df2["tabla"] == tabla].set_index("columna")

        # Columnas que faltan
        for col in cols_db1.index.difference(cols_db2.index):
            columnas_faltantes.append({"tabla": tabla, "columna": col, "falta_en": db2_name})
        for col in cols_db2.index.difference(cols_db1.index):
            columnas_faltantes.append({"tabla": tabla, "columna": col, "falta_en": db1_name})

        # Columnas en común -> comparar atributos lado a lado
        for col in cols_db1.index.intersection(cols_db2.index):
            row1 = cols_db1.loc[col]
            row2 = cols_db2.loc[col]

            if (
                (row1["tipo"] != row2["tipo"])
                or (row1["nullable"] != row2["nullable"])
                or (row1["primary_key"] != row2["primary_key"])
            ):
                diferencias_columnas.append(
                    {
                        "tabla": tabla,
                        "columna": col,
                        f"tipo_{db1_name}": row1["tipo"],
                        f"tipo_{db2_name}": row2["tipo"],
                        f"nullable_{db1_name}": row1["nullable"],
                        f"nullable_{db2_name}": row2["nullable"],
                        f"pk_{db1_name}": row1["primary_key"],
                        f"pk_{db2_name}": row2["primary_key"],
                    }
                )

    df_columnas_faltantes = pd.DataFrame(columnas_faltantes)
    df_diferencias_columnas = pd.DataFrame(diferencias_columnas)
    logging.info(f"Columnas faltantes: {len(df_columnas_faltantes)}")
    logging.info(f"Diferencias de columnas: {len(df_diferencias_columnas)}")

    # Índices
    df_indices_diff = pd.merge(
        idx1, idx2, on=["tabla", "nombre_indice"], how="outer", suffixes=(f"_{db1_name}", f"_{db2_name}")
    )

    df_indices_diff = df_indices_diff[
        (df_indices_diff[f"columnas_{db1_name}"] != df_indices_diff[f"columnas_{db2_name}"])
        | (df_indices_diff[f"unico_{db1_name}"] != df_indices_diff[f"unico_{db2_name}"])
    ]
    logging.info(f"Diferencias en índices: {len(df_indices_diff)}")

    # Foreign Keys
    df_fk_diff = pd.merge(fk1, fk2, on=["tabla", "fk_nombre"], how="outer", suffixes=(f"_{db1_name}", f"_{db2_name}"))

    df_fk_diff = df_fk_diff[
        (df_fk_diff[f"columnas_{db1_name}"] != df_fk_diff[f"columnas_{db2_name}"])
        | (df_fk_diff[f"ref_tabla_{db1_name}"] != df_fk_diff[f"ref_tabla_{db2_name}"])
        | (df_fk_diff[f"ref_columnas_{db1_name}"] != df_fk_diff[f"ref_columnas_{db2_name}"])
    ]
    logging.info(f"Diferencias en Foreign Keys: {len(df_fk_diff)}")

    # Comentarios de tablas
    df_tab_comments = pd.merge(
        tbl_comments1, tbl_comments2, on="tabla", how="inner", suffixes=(f"_{db1_name}", f"_{db2_name}")
    )
    df_tab_comments = df_tab_comments[
        df_tab_comments[f"comentario_{db1_name}"] != df_tab_comments[f"comentario_{db2_name}"]
    ]
    logging.info(f"Diferencias en comentarios tablas: {len(df_tab_comments)}")

    # Comentarios de columnas
    df_col_comments = pd.merge(
        col_comments1, col_comments2, on=["tabla", "columna"], how="inner", suffixes=(f"_{db1_name}", f"_{db2_name}")
    )
    df_col_comments = df_col_comments[
        df_col_comments[f"comentario_{db1_name}"] != df_col_comments[f"comentario_{db2_name}"]
    ]
    logging.info(f"Diferencias en comentarios columnas: {len(df_col_comments)}")

    # Comparar definiciones de vistas
    df_views_db1["def_normalizada"] = df_views_db1["definicion"].apply(normalize_view_definition)
    df_views_db2["def_normalizada"] = df_views_db2["definicion"].apply(normalize_view_definition)

    df_views_diff = pd.merge(
        df_views_db1, df_views_db2, on="vista", how="outer", suffixes=(f"_{db1_name}", f"_{db2_name}")
    )
    # llenar NaN con "" para evitar errores de comparación
    df_views_diff[f"def_normalizada_{db1_name}"] = df_views_diff[f"def_normalizada_{db1_name}"].fillna("")
    df_views_diff[f"def_normalizada_{db2_name}"] = df_views_diff[f"def_normalizada_{db2_name}"].fillna("")
    df_views_diff = df_views_diff[
        df_views_diff[f"def_normalizada_{db1_name}"] != df_views_diff[f"def_normalizada_{db2_name}"]
    ]
    logging.info(f"Diferencias en vistas: {len(df_views_diff)}")

    # Compara Procedures
    # procedures diferencias (normalizadas)
    df_procs_diff = pd.merge(
        df_procs_db1, df_procs_db2, on="procedure", how="outer", suffixes=(f"_{db1_name}", f"_{db2_name}")
    )
    df_procs_diff[f"def_normalizada_{db1_name}"] = df_procs_diff[f"def_normalizada_{db1_name}"].fillna("")
    df_procs_diff[f"def_normalizada_{db2_name}"] = df_procs_diff[f"def_normalizada_{db2_name}"].fillna("")
    df_procs_diff = df_procs_diff[
        df_procs_diff[f"def_normalizada_{db1_name}"] != df_procs_diff[f"def_normalizada_{db2_name}"]
    ]

    # -------------------------------
    # GUARDAR RESULTADOS
    # -------------------------------
    with pd.ExcelWriter(OUTPUT_EXCEL) as writer:
        df_tablas_faltantes.to_excel(writer, sheet_name="tablas_faltantes", index=False)
        df_columnas_faltantes.to_excel(writer, sheet_name="columnas_faltantes", index=False)
        df_diferencias_columnas.to_excel(writer, sheet_name="diferencias_columnas", index=False)
        df_indices_diff.to_excel(writer, sheet_name="indices_diferentes", index=False)
        df_fk_diff.to_excel(writer, sheet_name="foreign_keys_diferentes", index=False)
        df_tab_comments.to_excel(writer, sheet_name="dif_comentarios_tablas", index=False)
        df_col_comments.to_excel(writer, sheet_name="dif_comentarios_columnas", index=False)
        df_views_diff.to_excel(writer, sheet_name="vistas_diferentes", index=False)
        df_procs_diff.to_excel(writer, sheet_name="procedures_diferentes", index=False)

    # -------------------------------
    # GENERAR SCRIPTS SQL EN AMBAS DIRECCIONES
    # -------------------------------
    OUTPUT_SQL_db1_db2 = Path(f"salida/sync_{db1_name}_from_{db2_name}.sql")
    OUTPUT_SQL_db2_db1 = Path(f"salida/sync_{db2_name}_from_{db1_name}.sql")
    generar_script_sql(
        df2, df1, df_tab_comments, df_col_comments, idx2, idx1, fk2, fk1, db2_name, db1_name, OUTPUT_SQL_db1_db2
    )
    generar_script_sql(
        df1, df2, df_tab_comments, df_col_comments, idx1, idx2, fk1, fk2, db1_name, db2_name, OUTPUT_SQL_db2_db1
    )

    OUTPUT_SQL_db1_db2_critico = Path(f"salida/sync_{db1_name}_from_{db2_name}_critico.sql")
    OUTPUT_SQL_db2_db1_critico = Path(f"salida/sync_{db2_name}_from_{db1_name}_critico.sql")
    generar_sql_critico(
        df2, df1, df_tab_comments, df_col_comments, idx2, idx1, fk2, fk1, db2_name, db1_name, OUTPUT_SQL_db1_db2_critico
    )
    generar_sql_critico(
        df1, df2, df_tab_comments, df_col_comments, idx1, idx2, fk1, fk2, db1_name, db2_name, OUTPUT_SQL_db2_db1_critico
    )

    ############## VISTAS #############
    OUTPUT_SQL_db1_db2_critico_vistas = Path(f"salida/sync_{db1_name}_from_{db2_name}_vistas.sql")
    OUTPUT_SQL_db2_db1_critico_vistas = Path(f"salida/sync_{db2_name}_from_{db1_name}_vistas.sql")

    # Vistas: DB1 -> DB2
    generar_sql_views_critico(df_views_diff, db1_name, db2_name, OUTPUT_SQL_db2_db1_critico_vistas)

    # Para DB2 -> DB1, invertir origen/destino
    df_views_diff_reverse = df_views_diff.copy()
    df_views_diff_reverse[f"definicion_{db1_name}"], df_views_diff_reverse[f"definicion_{db2_name}"] = (
        df_views_diff_reverse[f"definicion_{db2_name}"],
        df_views_diff_reverse[f"definicion_{db1_name}"],
    )

    generar_sql_views_critico(df_views_diff_reverse, db2_name, db1_name, OUTPUT_SQL_db1_db2_critico_vistas)

    ############## PROCEDURES #############
    OUTPUT_SQL_db1_db2_critico_proc = Path(f"salida/sync_{db1_name}_from_{db2_name}_proc.sql")
    OUTPUT_SQL_db2_db1_critico_proc = Path(f"salida/sync_{db2_name}_from_{db1_name}_proc.sql")

    # DB1 -> DB2
    generar_sql_procs_critico(df_procs_diff, db2_name, db1_name, OUTPUT_SQL_db2_db1_critico_proc)
    # generar_sql_procs_critico(df_procs_diff.assign(definicion_db1=df_procs_diff.get(f"definicion_{db1_name}")), db1_name, db2_name, OUTPUT_SQL_db2_db1_critico_proc)

    # DB2 -> DB1
    df_procs_diff_reverse = df_procs_diff.copy()
    df_procs_diff_reverse[f"def_normalizada_{db1_name}"], df_procs_diff_reverse[f"def_normalizada_{db2_name}"] = (
        df_procs_diff_reverse[f"def_normalizada_{db2_name}"],
        df_procs_diff_reverse[f"def_normalizada_{db1_name}"],
    )
    df_procs_diff_reverse[f"definicion_{db1_name}"], df_procs_diff_reverse[f"definicion_{db2_name}"] = (
        df_procs_diff_reverse[f"definicion_{db2_name}"],
        df_procs_diff_reverse[f"definicion_{db1_name}"],
    )
    generar_sql_procs_critico(df_procs_diff_reverse, db1_name, db2_name, OUTPUT_SQL_db1_db2_critico_proc)

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
