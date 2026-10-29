"""``NUMBER`` de Oracle sin pasar por ``float`` en las consultas personalizadas y nombradas (v5.1.0, G44 de util_bbdd_web).

python-oracledb devuelve como ``float`` un ``NUMBER`` con escala (``NUMBER(38,3)``) o sin restricción y no entero
(``1.5``), y pierde precisión (``12345678901234567.891`` → ``1.2345678901234568e+16``). El conversor lee esas columnas
como texto y da ``Decimal`` (o ``int`` si el valor sin restricción es entero), como ya hacen PostgreSQL y MySQL.

Se pone solo en el cursor de cada consulta: ni la conexión ni ``oracledb.defaults`` cambian, así que el catálogo y el
resto de consultas internas siguen igual. ``FLOAT`` (precisión > 0, escala -127), ``BINARY_*`` y el resto no cambian.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

#: Escala que da oracledb a un ``NUMBER`` sin restricción y a ``FLOAT`` (los distingue la precisión: 0 en el primero).
_UNCONSTRAINED_SCALE = -127


def _to_decimal(value: str) -> Decimal:
    return Decimal(value)


def _to_int_or_decimal(value: str) -> int | Decimal:
    number = Decimal(value)
    exponent = number.as_tuple().exponent
    return int(number) if isinstance(exponent, int) and exponent >= 0 else number


def oracle_output_type_handler(cursor: Any, metadata: Any) -> Any:
    """``outputtypehandler`` de oracledb: ``NUMBER`` con escala → ``Decimal``; sin restricción → ``int`` o ``Decimal``.

    Args:
        cursor: Cursor de oracledb (síncrono o asíncrono) que ejecuta la consulta.
        metadata: ``oracledb.FetchInfo`` de la columna.

    Returns:
        La variable de lectura como texto con su conversor, o ``None`` para dejar la columna como la da el driver.
    """
    import oracledb

    if metadata.type_code is not oracledb.DB_TYPE_NUMBER:
        return None
    precision = metadata.precision or 0
    scale = metadata.scale or 0
    if scale > 0:
        converter: Any = _to_decimal
    elif precision == 0 and scale in (0, _UNCONSTRAINED_SCALE):
        converter = _to_int_or_decimal
    else:  # NUMBER(p) y NUMBER(p, s<0) ya son int; FLOAT (p > 0, s = -127) sigue siendo float
        return None
    return cursor.var(oracledb.DB_TYPE_VARCHAR, arraysize=cursor.arraysize, outconverter=converter)


def prepare_query_cursor(conn: Any, cursor: Any) -> None:
    """Pone ``oracle_output_type_handler`` en ``cursor`` si ``conn`` es de oracledb y no tiene ya un conversor propio.

    El driver se detecta por el módulo de la conexión, como ``SyncQueryExecutor._is_mariadb_connection``.
    """
    if not str(type(conn).__module__).startswith("oracledb"):
        return
    if getattr(conn, "outputtypehandler", None) is not None:  # el del usuario manda
        return
    cursor.outputtypehandler = oracle_output_type_handler
