# TRACEABILITY

## Session metadata
- id: 2026-10-26-web-gaps-ola2
- fecha: 2026-10-26
- rama: claude/practical-ride-44fot0
- skill: new_feature + version-closure
- fase: IMPLEMENT + AUDIT_CODE + VERSION de la ola 2 (v4.2.0)

## Prompt issued
Continuar con la ola 2 del plan de huecos de util_bbdd_web (comparación de esquemas, util_bbdd 4.2.0). Plan canónico:
`docs/plan/UTIL_BBDD_GAPS_PLAN.md` de util_bbdd_web; resumen en `.ai/sessions/2026-10-25-web-gaps-plan/PLAN.md`.

## Context sources
- `src/util_bbdd/comparar/` (comparator, models, reporters HTML y fachada) en 4.1.0 + `e049d71`.
- Paquete npm `mermaid@10.9.8` (tarball verificado con la `integrity` sha512 del registro) para calcular el SRI.

## AI output summary
- Un commit por fase (ruff, ruff format, mypy, pytest completo y `zensical build --strict` limpios en cada una):
  - U-C1 `22c0282` G23: etiquetas `motor [schema]` sin datos de conexión; `source_label`/`target_label`.
  - U-C2 `8edbf8e` G24: `SchemaDiff.to_dict()`/`from_dict()` con `format` y `format_version` 1.
  - U-C3 `3bbd60e` G25: `mermaid@10.9.8` con SRI, script del informe sin dependencia de Mermaid y `mermaid_src`.
    Verificado en Chromium (Playwright) sin red: controles operativos con Mermaid bloqueado; con el fichero local
    incrustado se dibujan los diagramas.
  - U-C4 `60e3c5f` G1: `on_progress`/`cancel_token` en `SchemaComparator.compare()` (operación `"compare"`).
  - U-C5 (opcional, G7): no se hace en esta ola.
- VERSION: `release: v4.2.0` (este commit). Tag y wheel los publica el propietario tras el merge.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Ola 2 | `src/util_bbdd/comparar/` | completado (v4.2.0) |

## Directrices para Futuras IAs
- **[comparar]**: las etiquetas por defecto salen de `_engine_name` + `_effective_schema` (schema pedido →
  `default_schema_name` → usuario en Oracle / BD en MariaDB-MySQL); nunca de la URL renderizada.
- **[comparar]**: con `source_label`/`target_label`, el nombre de fichero usa la etiqueta (saneada por
  `sanitize_filename`), no la etiqueta corta.
- **[comparar]**: `SchemaDiff.from_dict` valida contra las anotaciones de los dataclasses (`typing.get_type_hints`):
  un campo nuevo con valor por defecto no exige subir `FORMAT_VERSION`.
- **[comparar]**: cambiar `MERMAID_VERSION` exige recalcular `MERMAID_SRI` sobre `dist/mermaid.min.js` del tarball de
  npm (jsDelivr no es accesible desde el contenedor; el registro de npm sí).
- **[comparar]**: `SchemaComparatorProtocol` no se amplía con los parámetros nuevos (romper implementaciones de
  terceros sería MAJOR).

## Veredicto final
Veredicto: GO (ola 2, v4.2.0)
Pendientes al cierre:
- Merge a `develop`/`main`, tag `v4.2.0` y wheel + `.sha256` en GitHub Releases (propietario).
- Olas 3-6 en sesiones aparte.
