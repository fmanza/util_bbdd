"""Construcción de sentencias DDL desde metadatos de base de datos.

Responsabilidad: Construir sentencias SQL (CREATE TABLE, etc.) basadas en
metadatos obtenidos de la base de datos.
"""

from typing import Any


class DDLBuilder:
    """Construye sentencias DDL desde metadatos de BD.

    Responsabilidad única: Transformar filas de columnas en sentencias DDL
    válidas para cada motor de base de datos.
    """

    def __init__(self, db_type: str = "mariadb"):
        """Inicializa constructor de DDL.

        Args:
            db_type: Tipo de base de datos (mariadb, postgresql, oracle, etc.)
        """
        self.db_type = db_type.lower()

    def build_create_table_from_columns(
        self,
        table_name: str,
        columns: list[tuple],
        primary_keys: list[str] | None = None,
    ) -> str:
        """Construye sentencia CREATE TABLE a partir de columnas.

        Args:
            table_name: Nombre de la tabla
            columns: Lista de tuplas de columnas
            primary_keys: Lista de nombres de PKs (opcional)

        Returns:
            Sentencia CREATE TABLE formatted
        """
        if not columns:
            return ""

        # Construir definición de columnas
        column_defs = []
        for col in columns:
            if self._is_valid_column(col):
                col_def = self._build_column_definition(col)
                if col_def:
                    column_defs.append(col_def)

        if not column_defs:
            return ""

        # Agregar constraint de PK si existe
        if primary_keys:
            pk_constraint = self._build_primary_key_constraint(primary_keys)
            if pk_constraint:
                column_defs.append(pk_constraint)

        # Formatear CREATE TABLE
        table_id = self._quote_identifier(table_name)
        return f"CREATE TABLE {table_id} (\n" + ",\n".join(column_defs) + "\n)"

    def _is_valid_column(self, col: Any) -> bool:
        """Valida que columna sea una tupla/lista válida.

        Args:
            col: Columna a validar

        Returns:
            True si es válida
        """
        return isinstance(col, (tuple, list)) and len(col) > 0

    def _build_column_definition(self, col: tuple) -> str:
        """Construye definición de columna SQL.

        Args:
            col: Tupla de columna

        Returns:
            String con definición de columna
        """
        # Estructura típica: (nombre, tipo, nullable, ...)
        if len(col) < 2:
            return ""

        col_name = str(col[0]).strip()
        col_type = str(col[1]).strip() if col[1] else "VARCHAR(255)"

        if not col_name:
            return ""

        col_id = self._quote_identifier(col_name)
        col_def = f"{col_id} {col_type}"

        # Agregar NOT NULL si existe en posición 2
        if len(col) > 2 and col[2] is not None:
            nullable = col[2]
            if isinstance(nullable, str):
                nullable = nullable.upper() == "NO"
            if nullable:
                col_def += " NOT NULL"

        # Agregar DEFAULT si existe en posición 4
        if len(col) > 4 and col[4] is not None:
            default = str(col[4]).strip()
            if default and default.upper() != "NONE":
                col_def += f" DEFAULT {default}"

        return col_def

    def _build_primary_key_constraint(self, pk_columns: list[str]) -> str:
        """Construye constraint de PRIMARY KEY.

        Args:
            pk_columns: Lista de nombres de columnas que forman PK

        Returns:
            String con constraint PRIMARY KEY
        """
        if not pk_columns:
            return ""

        pk_cols = ", ".join(self._quote_identifier(col) for col in pk_columns)
        return f"PRIMARY KEY ({pk_cols})"

    def _quote_identifier(self, identifier: str) -> str:
        """Escapa identificador según motor de BD.

        Args:
            identifier: Nombre a escapar

        Returns:
            Identificador escapado
        """
        if self.db_type in ("postgresql",):
            return f'"{identifier}"'
        elif self.db_type in ("mariadb", "mysql", "sqlite"):
            return f"`{identifier}`"
        elif self.db_type in ("oracle",):
            return f'"{identifier}"'
        elif self.db_type in ("sqlserver",):
            return f"[{identifier}]"
        else:
            return f"`{identifier}`"
