"""Utilidades SQL compartidas dentro del módulo dump.

Re-exporta el quoting de identificadores de ``bulk`` (fuente única) para ``orchestrator``, ``_constraints`` e
``_indexes``, y sanea los mensajes de error que el volcado guarda en sus resultados (:func:`error_message`).
"""

from __future__ import annotations

import re

from ..bulk._support.sql_quoting import quote_identifier, quote_table

#: Valores de filas que algunos motores ponen en la primera línea del error (G34 de util_bbdd_web, 4.4.0). Se cambian
#: por ``…``; los nombres de clave, columna, tabla y constraint se conservan. Las expresiones son codiciosas hasta el
#: texto fijo que sigue al valor, para que un valor con comillas o paréntesis no deje una parte a la vista.
_MASKED_QUOTED = r"\1'…'"
_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # MySQL/MariaDB: Duplicate entry '<v>' for key '<k>'
    (re.compile(r"(Duplicate entry )'.*'(?= for key)"), _MASKED_QUOTED),
    # MySQL/MariaDB: Incorrect integer value: '<v>' for column '<c>' (también datetime, decimal, string…)
    (re.compile(r"(value: )'.*'(?= for column)"), _MASKED_QUOTED),
    # SQL Server: The duplicate key value is (<v>).
    (re.compile(r"(duplicate key value is )\(.*?\)(?=\.|\s|$)"), r"\1(…)"),
    # SQL Server: Conversion failed when converting the varchar value '<v>' to data type int.
    (re.compile(r"(converting the \w+ value )'.*'(?= to data type)"), _MASKED_QUOTED),
    # SQL Server 2019+: String or binary data would be truncated in table '<t>', column '<c>'. Truncated value: '<v>'.
    (re.compile(r"(Truncated value: )'.*'"), _MASKED_QUOTED),
    # PostgreSQL: invalid input syntax for type integer: "<v>"
    (re.compile(r'(invalid input syntax for type [\w ]+: )".*"'), r'\1"…"'),
    # PostgreSQL: invalid input value for enum <t>: "<v>"
    (re.compile(r'(invalid input value for enum \S+: )".*"'), r'\1"…"'),
)
_URL = re.compile(r"\b[a-z][a-z0-9+]*://\S+")


def error_message(error: BaseException | str) -> str:
    """Mensaje de error sin datos de negocio, para ``error_msg`` de los resultados del volcado (G34, 4.4.0).

    Se queda con la primera línea: los errores de SQLAlchemy añaden después la sentencia (``[SQL: …]``), sus
    parámetros (``[parameters: …]``, filas del origen) y el enlace de ayuda; PostgreSQL pone la clave repetida en
    ``DETAIL`` y Oracle 23ai los valores en ``ORA-03301``, ambos en líneas siguientes. De esa línea quita una URL de
    conexión y enmascara los valores que MySQL/MariaDB, SQL Server y PostgreSQL ponen en ella (:data:`_VALUE_PATTERNS`).

    Args:
        error: Excepción o texto ya formado (p. ej. un error de partición de ``ParallelBulkLoader``).

    Returns:
        El mensaje saneado; el nombre de la clase si la excepción no tiene texto.

    Examples:
        >>> error_message("Violation of PRIMARY KEY 'PK_t'. The duplicate key value is (42).\\n[SQL: INSERT …]")
        "Violation of PRIMARY KEY 'PK_t'. The duplicate key value is (…)."
    """
    text = str(error).strip()
    if not text:
        return type(error).__name__ if isinstance(error, BaseException) else ""
    line = text.splitlines()[0]
    line = line.split("[SQL:")[0].split("(Background on this error")[0].strip()
    line = _URL.sub("[url]", line)
    for pattern, replacement in _VALUE_PATTERNS:
        line = pattern.sub(replacement, line)
    return line


__all__: list[str] = ["error_message", "quote_identifier", "quote_table"]
