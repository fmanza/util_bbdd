# TRACEABILITY

## Session metadata
- id: 2026-09-26r-refactor-dump-audit-summary-tail
- fecha: 2026-09-26
- rama: develop (base `185f7b2`)
- skill: refactor (rendimiento, sin cambio funcional)
- origen: paso 3.4 / PF-08 del roadmap `2026-09-25b-performance-audit-dump-delta` (Fase 3, primer paso por menor riesgo)

## Objetivo
El resumen de auditoría del volcado (`_build_audit_summary`) cargaba el CSV histórico completo en cada volcado y filtraba
por `timestamp >= inicio`: 0,72 s con 500K registros, 2,9 s con 2M (lineal, ≈ 1,4 µs/registro, 60 % en `read_csv`).

## Cambio
- `dump/orchestrator.py`:
  - `run()` guarda el tamaño del CSV al empezar (`_audit_start_offset`, vía `_file_size`).
  - `_read_audit_csv(path, start_offset)` (nuevo): lee la cabecera y lo escrito desde ese desplazamiento, con las mismas conversiones que `AuditManager.leer_auditoria` (`timestamp` con `format="mixed"`, `tiempo_seg` con coma decimal). Si el desplazamiento cae a mitad de una fila (otro proceso escribía), salta a la siguiente. Sin desplazamiento, o si el fichero es ahora más pequeño (truncado o rotado), lee el fichero entero como antes.
  - `_build_audit_summary` acepta `start_offset` (por defecto `None`: comportamiento anterior) y mantiene el mismo filtro por timestamp y el mismo aviso si difiere de `audited_rows`.
- Incidencia de la sesión: dos literales (`b"\n"`, `"\t"`) llegaron al fichero como caracteres reales por el escapado del shell; se corrigieron y se revisaron todos los ficheros tocados en la sesión (sin NUL ni tabuladores inesperados).

## Validación
- **Tests** (`tests/unit/dump/test_audit_summary_offset.py`, 7): resumen con desplazamiento **igual** al de lectura completa; solo se analizan filas nuevas (tipos correctos); desplazamiento a mitad de fila; fichero encogido → lectura completa; sin desplazamiento (`None`/0) → completa; fichero creado durante el volcado.
- **Calidad**: `ruff` limpio; `mypy src` limpio; `pytest tests/unit`: **4604 passed**.
- **A/B intercalado** (PostgreSQL `large`, variante `audit_history` con 500K registros previos): `audit_summary` 0,694 · 0,691 s → **0,012 · 0,012 s**; resumen idéntico (175 operaciones, 3.500.000 filas, `audited_rows` igual); total 13,2 · 12,5 → 12,0 · 11,9 s.

## VERSION
- Commit: `refactor(dump): resumen de auditoría leyendo solo lo añadido al CSV (3.4)`
- API pública: sin cambios (parámetro nuevo en un método privado). Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump/audit]**: el resumen del volcado lee el CSV desde el tamaño que tenía al empezar; si cambias el formato del CSV en `bulk._audit.repository`, actualiza también `_read_audit_csv`.
- **[herramientas]**: al escribir código con `\n`, `\t` o `\x00` desde un heredoc en esta sesión, el escapado se perdió dos veces; comprueba los bytes del fichero tras escribir literales con barra invertida.

## Veredicto final
Veredicto: CLOSED
