# CONTEXT SNAPSHOT

## Estado del repositorio al inicio
- rama: `develop`
- último commit: `3c8e255 docs: reorganizar navegación, añadir guías y consolidar tuning de bulk`
- versión `pyproject.toml`: 0.10.0
- working tree: limpio al inicio de la sesión

## Valores por defecto previos (módulo migrate)
| Constante | Valor previo | Valor nuevo |
|---|---|---|
| `DEFAULT_CHARSET` | `utf8mb4` | `utf8mb4` (sin cambio) |
| `DEFAULT_COLLATION` | `utf8mb4_unicode_ci` | `utf8mb4_uca1400_ai_ci` |

## Punto de validación
- `MigrationPlanner` valida charset/collation en el constructor vía
  `validate_charset` / `validate_collation` / `validate_charset_collation_pair`
  (`src/util_bbdd/migrate/charset.py`).
- El nuevo default debe estar presente en `VALID_COLLATIONS` y en
  `CHARSET_COLLATION_MAP["utf8mb4"]` para no romper la validación por defecto.

## Compatibilidad
- `utf8mb4_uca1400_ai_ci` es una collation de **MariaDB ≥ 10.10** (UCA 14.0.0,
  acento-insensible y mayúsculas-insensible). No existe en MySQL ni en MariaDB previas.
- Implicación: las migraciones generadas con el default ahora requieren MariaDB ≥ 10.10;
  para versiones previas hay que pasar `collation=` explícito.

## Gate G0
- **Veredicto: GO** — cambio acotado, opción previa preservada como válida,
  riesgo de compatibilidad documentado.
