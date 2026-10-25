# Huecos detectados por util_bbdd_web: fases en util_bbdd

Resumen para trabajar desde este repositorio. **Fuente canónica** (orden, fases de la web, AUDIT_PLAN y
decisiones D1-D5): `docs/plan/UTIL_BBDD_GAPS_PLAN.md` de
[util_bbdd_web](https://github.com/fmanza/util_bbdd_web/blob/main/docs/plan/UTIL_BBDD_GAPS_PLAN.md); los huecos Gnn
están descritos en `docs/plan/UTIL_BBDD_GAPS.md` del mismo repositorio.

Reglas: un commit por fase; una release MINOR por ola con el wheel y su `.sha256` en GitHub Releases (la web lo
consume por URL, ADR-006 de la web); en 4.x solo parámetros opcionales nuevos, correcciones y `FutureWarning`.

| Ola | Release | Fases (commit cada una) |
|---|---|---|
| 1 | 4.1.0 | U-0.1 contrato de progreso/cancelación en `audit/progress.py` (G1) · U-0.2 extras `sqlserver`, `hsqldb`, `sqlite-async` (G3) · U-D1 ventana de salida por instancia (G2) · U-D2 capturar `graphviz.CalledProcessError` por diagrama (G39) · U-D3 `orthogonal_edges` (G39) · U-D4 validar estilos de `plantilla_word` (G41) · U-D5 tabla sin relaciones en HTML (G38) · U-D6 schema explícito en Oracle en `MetadataContextResolver` (G21) · U-D7 argumento `schema` en `DatabaseDocumentation` y `GraphvizRelationshipGraphExt` (G22) · U-D8 `plantilla_excel` y colores del tema (G40) · U-D9 progreso en `generate()` (G1) · U-G1 progreso en los grafos (G1) |
| 2 | 4.2.0 | U-C1 `source_label`/`target_label` sin datos de conexión (G23) · U-C2 `SchemaDiff.to_dict/from_dict` (G24) · U-C3 Mermaid con versión fija + SRI y degradación (G25) · U-C4 progreso en `compare()` (G1) · U-C5 opcional: `SchemaSnapshot` en `compare()` (G7) |
| 3 | 4.3.0 | U-M1 consulta pública de motores de migración (G4) · U-M2 tipo de la FK = tipo de la columna referenciada (G28) · U-M3 `MigrationPlan.to_dict/from_dict` (G26) · U-M4 `check_target()` y `dry_run` (G27) · U-M5 progreso en `execute()` (G1) |
| 4 | 4.4.0 | U-V1 `DumpOrchestrator.plan()` (G29) · U-V2 eventos de auditoría durante el volcado (G6) · U-V3 diario y `restore_constraints()` (G31) · U-V4 `isolate` con ORA-00001 (G32) · U-V5 fechas ISO de SQLite (G33) · U-V6 `error_msg` sin datos (G34) · U-V7 `FutureWarning` de `truncate_target` (G30) · U-V8 progreso y cancelación con restauración (G1) |
| 5 | 4.5.0 | U-B1 contadores de filas fiables (G37) · U-B2 `ParallelPlan.atomic` (G36) · U-B3 `dry_run` y `FutureWarning` de `generar_sql` (G35) · U-B4 progreso y cancelación por lote (G1) |
| 6 | 4.6.0 | U-T1 `get_engine_capabilities` y `get_driver_status` (G5, G10) · U-T2 fuera `cx_Oracle` y `default_driver` (G8, G14) · U-T3 `kind` por parámetro (G12) · U-T4 `build_conn_params` conserva opcionales (G15) · U-T5 `get_database_info` sin secretos (G11) · U-T6 `ping`, `get_server_version`, `get_schema_names` (G13, G17) · U-T7 validar todos los parámetros de queries (G18) · U-T8 `read_only` y `max_rows` en `execute_custom_*` (G19, G20) |
| 8 *(opcional)* | 5.0.0 | Valores por defecto seguros: `truncate_target=False`, `generar_sql=False`, ventana de G2 = 0 |
