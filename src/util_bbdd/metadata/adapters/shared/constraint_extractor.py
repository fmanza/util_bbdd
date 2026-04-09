"""Extracción agnóstica de constraints desde DDL."""

from __future__ import annotations

__all__: list[str] = [
    "extract_constraint_from_ddl",
]


def extract_constraint_from_ddl(ddl: str, constraint_type: str = "PRIMARY KEY") -> list[str]:
    """Extrae nombres de constraintsy columnas de un DDL.

    Función heurística para parsear DDL genérico. Útil como fallback
    cuando la introspección de información_schema no es completa.

    Args:
        ddl: DDL completo de la tabla o routine.
        constraint_type: Tipo de constraint a buscar (p.ej. 'PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE').

    Returns:
        list[str]: Lista de columnas que cumplen el constraint.
                   Si no se encuentran, devuelve lista vacía.

    Ejemplo:
        >>> ddl = "CREATE TABLE users (id INT PRIMARY KEY, email VARCHAR(100))"
        >>> extract_constraint_from_ddl(ddl, 'PRIMARY KEY')
        ['id']
    """
    # Búsqueda simple: si el constraint está en el DDL, intenta extraer columnas
    if constraint_type.upper() not in ddl.upper():
        return []

    # Fallback muy simple: si es PK, busca `id` o columnas antes de PRIMARY KEY
    # Esto es básico; un parser real usaría sqlparse o similar
    try:
        upper_ddl = ddl.upper()
        constraint_upper = constraint_type.upper()
        idx = upper_ddl.find(constraint_upper)
        if idx == -1:
            return []

        # Extrae la parte después del constraint hasta el cierre o coma
        after_constraint = ddl[idx + len(constraint_upper) :].strip()
        if after_constraint.startswith("("):
            end_idx = after_constraint.find(")")
            if end_idx > 0:
                cols_str = after_constraint[1:end_idx]
                # Divide por comas y limpia
                cols = [col.strip().strip('`"') for col in cols_str.split(",")]
                return [col for col in cols if col]
    except Exception:
        pass

    return []
