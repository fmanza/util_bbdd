# TRACEABILITY

## Session metadata
- id: 2026-10-01y-ora03106-repro
- fecha: 2026-10-01
- rama: develop
- flujo: Fase C del plan `../2026-10-01v-plan-pendientes-mariadb-connector/PLAN_AUDIT_PLAN.md` (D-4: preparar, publica el
  usuario)

## AI output summary
- `ora03106_minimal.py`: reproducción solo con oracledb (sin util_bbdd), credenciales por variables de entorno o desde
  la URL del banco (`--from-sqlalchemy-url`; la contraseña no se imprime). Ejecutada con 4.0.1 (venv del proyecto) y con
  4.0.2 y 26.0.1 en venvs aparte del scratchpad (el del proyecto no cambia). Matriz: `ora03106_matrix.log`.
- Resultado: UPDATE + `batcherrors=True` + valor de más de 8000 caracteres + una fila con ORA-12899 → ORA-03106 con
  bind `str` en las tres versiones, y con bind `DB_TYPE_CLOB` solo en 26.0.1 (regresión); INSERT nunca; sin
  `batcherrors`, ORA-12899 normal. Servidor: Oracle AI Database 26ai Free 23.26.3, AL32UTF8.
- `ISSUE_DRAFT.md`: borrador del issue en inglés para github.com/oracle/python-oracledb (**sin publicar**).
- La regla de `BulkCrud` (UPDATE con columnas LOB → bisección) cubre las tres versiones; comentario de `crud.py` y
  `docs/api/bulk_crud.md` actualizados con las versiones comprobadas.

## Validación
`ruff` limpio; `zensical build --strict` sin avisos. Sin cambios funcionales.

## Directrices para Futuras IAs
- **[bulk/oracle]**: actualizar oracledb no quita la regla del UPDATE con LOB: 26.0.1 falla en más casos que 4.0.x.
  Volver a pasar `ora03106_minimal.py` con cada versión nueva antes de relajarla.
- **[externo]**: el issue no se publica sin confirmación del usuario.

## Veredicto final
Veredicto: CLOSED (pendiente: publicación del issue por el usuario)
