# REQUEST

## Session metadata
- id: 2026-05-22-comparar-short-report-names
- fecha: 2026-05-22
- rama: develop
- skill: refactor
- fase solicitada: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Solicitud original saneada
En `src\util_bbdd\comparar` el nombre de los reportes es demasiado largo. Optimizar y
acotarlo. Tiene que salir siempre el nombre del usuario o schema o database, según
corresponda el motor.

## Objetivo operativo de esta sesión
- Generar nombres de fichero de reporte compactos (< 40 caracteres de stem) en lugar
  de la URL completa sanitizada (130+ caracteres).
- Garantizar que el stem siempre contenga el identificador más relevante según el motor:
  usuario (Oracle), schema o database (PostgreSQL), database (MariaDB/MySQL/MSSQL),
  stem de fichero (SQLite).
- No cambiar los labels de display en el cuerpo de los reportes ni la API pública.
- Cobertura de regresión: todos los tests existentes deben seguir pasando.

## Restricciones explícitas
- No cambiar `_build_label()` ni los campos `source_label` / `target_label` (display en reportes).
- No romper retrocompatibilidad de `SchemaDiff` (campos nuevos con `default=""`).
- No introducir cambios funcionales; solo refactor de nombres de fichero.

## Resultado esperado
- Nuevos campos `source_short_label` / `target_short_label` en `SchemaDiff`.
- Nuevo método estático `_build_short_label()` + `_pick_identifier()` en `SchemaComparator`.
- `build_output_stem()` usa los short labels cuando están disponibles.
- 11 tests nuevos en `TestBuildShortLabel`.
- `ruff check` + `mypy` + `pytest` verdes sobre el módulo `comparar`.
