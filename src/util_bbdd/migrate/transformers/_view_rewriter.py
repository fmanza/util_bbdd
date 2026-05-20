"""Reescritura best-effort de SQL Oracle en definiciones de vista.

Aplica sustituciones de texto/regex para los patrones Oracle más comunes sin
necesitar un parser SQL completo. Constructs que no tienen equivalente directo
(ROWNUM, CONNECT BY, outer-join (+), DECODE, LISTAGG) generan MigrationWarning
con severity="WARNING" y se dejan sin modificar en el SQL resultante.

Limitación conocida: las sustituciones son puramente léxicas y pueden producir
falsos positivos si los tokens sustituidos aparecen dentro de literales string
(por ejemplo ``'NVL is a function'``). La frecuencia real es muy baja en DDL
de vistas.
"""

from __future__ import annotations

import re

from dataclasses import replace as _dc_replace

from ..ir.models import CanonicalView, MigrationWarning

# ─── Patrones de sustitución simple ──────────────────────────────────────────

# Hints del optimizador Oracle: /*+ ... */  (puede ser multilínea)
_HINT_RE = re.compile(r"/\*\+.*?\*/", re.DOTALL)

# NVL(a, b) → COALESCE(a, b)  — solo la función de dos argumentos
_NVL_RE = re.compile(r"\bNVL\s*\(", re.IGNORECASE)

# FROM DUAL al final de una subconsulta o SELECT escalar
_FROM_DUAL_RE = re.compile(r"\s+FROM\s+DUAL\b", re.IGNORECASE)

# ─── Patrones que requieren revisión manual ───────────────────────────────────

_COMPLEX_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bROWNUM\b", re.IGNORECASE), "ROWNUM"),
    (re.compile(r"\bCONNECT\s+BY\b", re.IGNORECASE), "CONNECT BY"),
    (re.compile(r"\bSTART\s+WITH\b", re.IGNORECASE), "START WITH"),
    (re.compile(r"\(\s*\+\s*\)", re.IGNORECASE), "outer join (+)"),
    (re.compile(r"\bDECODE\s*\(", re.IGNORECASE), "DECODE"),
    (re.compile(r"\bNVL2\s*\(", re.IGNORECASE), "NVL2"),
    (re.compile(r"\bLISTAGG\s*\(", re.IGNORECASE), "LISTAGG"),
    (re.compile(r"\bWM_CONCAT\s*\(", re.IGNORECASE), "WM_CONCAT"),
    (re.compile(r"\bMODEL\b", re.IGNORECASE), "MODEL clause"),
]


def rewrite_oracle_view(
    view: CanonicalView,
    sysdate_fn: str,
    systimestamp_fn: str,
    user_fn: str,
    schema: str,
) -> CanonicalView:
    """Reescritura best-effort de SQL Oracle en una vista.

    Args:
        view: Vista canónica con SQL Oracle original.
        sysdate_fn: Función equivalente a SYSDATE en el motor destino.
        systimestamp_fn: Función equivalente a SYSTIMESTAMP en el motor destino.
        user_fn: Función equivalente a la pseudocolumna USER.
        schema: Nombre del schema Oracle (para strip de prefijos ``SCHEMA.``).

    Returns:
        Nueva CanonicalView con SQL reescrito y warnings acumulados.
        El objeto original no se modifica.
    """
    query = view.query
    warnings: list[MigrationWarning] = list(view.warnings)

    # 1. Strip hints del optimizador Oracle
    query = _HINT_RE.sub("", query)

    # 2. SYSDATE / SYSTIMESTAMP
    query = re.sub(r"\bSYSDATE\b", sysdate_fn, query, flags=re.IGNORECASE)
    query = re.sub(r"\bSYSTIMESTAMP\b", systimestamp_fn, query, flags=re.IGNORECASE)

    # 3. USER pseudocolumna
    query = re.sub(r"\bUSER\b", user_fn, query, flags=re.IGNORECASE)

    # 4. NVL(a, b) → COALESCE(a, b)
    query = _NVL_RE.sub("COALESCE(", query)

    # 5. FROM DUAL → eliminar (SELECT escalar no necesita tabla ficticia)
    query = _FROM_DUAL_RE.sub("", query)

    # 6. Strip prefijo de schema: SCHEMA_NAME. → vacío
    if schema:
        schema_re = re.compile(r"\b" + re.escape(schema) + r"\s*\.\s*", re.IGNORECASE)
        query = schema_re.sub("", query)

    # 7. Detectar constructs complejos → warnings (el SQL se deja sin modificar)
    for pattern, label in _COMPLEX_PATTERNS:
        if pattern.search(query):
            warnings.append(
                MigrationWarning(
                    table=view.name,
                    column=None,
                    oracle_type=label,
                    target_type="(revisión manual)",
                    message=(
                        f"Vista '{view.name}': construct Oracle '{label}' "
                        "no tiene equivalente automático; revisión manual requerida"
                    ),
                    severity="WARNING",
                )
            )

    return _dc_replace(view, query=query.strip(), warnings=warnings)


__all__: list[str] = ["rewrite_oracle_view"]
