"""Detección compartida del fallback silencioso al formatear valores DEFAULT.

Cada emisor (`oracle.py`, `postgresql.py`, `sqlserver.py`, `mariadb.py`) solo
reconoce las funciones `DEFAULT` de un dialecto origen "canónico" (Oracle o
MariaDB, según el emisor). `planner.py` reutiliza cada emisor para hasta 3
motores origen distintos, así que un `DEFAULT GETDATE()`/`CURDATE()` del motor
origen real que el emisor no reconoce cae al fallback genérico y se entrecomilla
como literal de texto — probablemente incorrecto, y hasta ahora silencioso.
"""

from __future__ import annotations

import re

from ..ir.models import MigrationWarning

_FUNCTION_CALL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*\([^()]*\)$")


def default_fallback_warning(
    *,
    raw_value: str,
    formatted_value: str,
    table: str,
    column: str,
    source_type: str,
    target_type: str,
) -> MigrationWarning | None:
    """Devuelve un ``MigrationWarning`` si el fallback de citado como string se activó
    sobre un valor con forma de llamada a función (``NOMBRE(...)``) no reconocida.

    No advierte sobre literales de texto genuinos sin forma de función (p.ej. un
    ``DEFAULT 'Pending'`` de Oracle): citarlos como string es el comportamiento
    correcto, no un fallback fallido.
    """
    if not _FUNCTION_CALL_RE.match(raw_value.strip()):
        return None
    if not (formatted_value.startswith("'") and formatted_value.endswith("'")):
        return None
    return MigrationWarning(
        table=table,
        column=column,
        oracle_type=source_type,
        target_type=target_type,
        message=(
            f"DEFAULT {raw_value} tiene forma de llamada a función pero no la reconoce este "
            f"emisor; se generó como literal de texto ({formatted_value}). Verifica manualmente "
            "si debía traducirse a una función equivalente del motor destino."
        ),
        severity="WARNING",
    )


__all__: list[str] = ["default_fallback_warning"]
