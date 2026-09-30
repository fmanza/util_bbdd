"""Reescritura best-effort de SQL Oracle en definiciones de vista.

Aplica sustituciones de texto/regex para los patrones Oracle más comunes sin
necesitar un parser SQL completo. Constructs que no tienen equivalente directo
(ROWNUM, CONNECT BY, outer-join (+), DECODE, LISTAGG) generan MigrationWarning
con severity="WARNING" y se dejan sin modificar en el SQL resultante.

Limitación conocida: las sustituciones son puramente léxicas y pueden producir
falsos positivos si los tokens sustituidos aparecen dentro de literales string
(por ejemplo ``'NVL is a function'``). La frecuencia real es muy baja en DDL
de vistas. MIG-07 (AUDIT_CODE 2026-09-22): toda sustitución léxica que
efectivamente modifique la query (SYSDATE, SYSTIMESTAMP, USER, NVL, FROM DUAL,
prefijo de schema) genera un MigrationWarning invitando a verificación manual
— antes solo USER lo generaba, pese a que el riesgo de falso positivo es el
mismo para las demás.
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


def _lexical_substitution_warning(view: CanonicalView, oracle_token: str, target: str, count: int) -> MigrationWarning:
    """Warning para una sustitución puramente léxica (MIG-07, ver módulo).

    Args:
        view: Vista sobre la que se aplicó la sustitución.
        oracle_token: Token/construct Oracle sustituido (p.ej. "SYSDATE").
        target: Texto por el que se sustituyó (o "(eliminado)" si se borra).
        count: Número de apariciones sustituidas.
    """
    plural = "s" if count > 1 else ""
    return MigrationWarning(
        table=view.name,
        column=None,
        category="VIEW",
        target_type=target,
        message=(
            f"Vista '{view.name}': {count} sustitución{plural} léxica de '{oracle_token}' "
            f"→ '{target}'; la sustitución es puramente textual (regex, sin parser SQL) y "
            "puede afectar apariciones dentro de literales de texto. Verificar manualmente."
        ),
        severity="WARNING",
    )


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
    query, sysdate_count = re.subn(r"\bSYSDATE\b", sysdate_fn, query, flags=re.IGNORECASE)
    if sysdate_count:
        warnings.append(_lexical_substitution_warning(view, "SYSDATE", sysdate_fn, sysdate_count))
    query, systimestamp_count = re.subn(r"\bSYSTIMESTAMP\b", systimestamp_fn, query, flags=re.IGNORECASE)
    if systimestamp_count:
        warnings.append(_lexical_substitution_warning(view, "SYSTIMESTAMP", systimestamp_fn, systimestamp_count))

    # 3. USER pseudocolumna
    if re.search(r"\bUSER\b", query, flags=re.IGNORECASE):
        query = re.sub(r"\bUSER\b", user_fn, query, flags=re.IGNORECASE)
        warnings.append(
            MigrationWarning(
                table=view.name,
                column=None,
                category="VIEW",
                target_type=user_fn,
                message=(
                    f"Vista '{view.name}': pseudocolumna USER sustituida por {user_fn}; "
                    "verificar que 'user' no sea el nombre de una columna"
                ),
                severity="WARNING",
            )
        )

    # 4. NVL(a, b) → COALESCE(a, b)
    query, nvl_count = _NVL_RE.subn("COALESCE(", query)
    if nvl_count:
        warnings.append(_lexical_substitution_warning(view, "NVL", "COALESCE", nvl_count))

    # 5. FROM DUAL → eliminar (SELECT escalar no necesita tabla ficticia)
    query, from_dual_count = _FROM_DUAL_RE.subn("", query)
    if from_dual_count:
        warnings.append(_lexical_substitution_warning(view, "FROM DUAL", "(eliminado)", from_dual_count))

    # 6. Strip prefijo de schema: SCHEMA_NAME. → vacío
    if schema:
        schema_re = re.compile(r"\b" + re.escape(schema) + r"\s*\.\s*", re.IGNORECASE)
        query, schema_prefix_count = schema_re.subn("", query)
        if schema_prefix_count:
            warnings.append(
                _lexical_substitution_warning(view, f"prefijo de schema '{schema}'", "(eliminado)", schema_prefix_count)
            )

    # 7. Detectar constructs complejos → warnings (el SQL se deja sin modificar)
    for pattern, label in _COMPLEX_PATTERNS:
        if pattern.search(query):
            warnings.append(
                MigrationWarning(
                    table=view.name,
                    column=None,
                    category="VIEW",
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
