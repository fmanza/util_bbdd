# TRACEABILITY

## Session metadata
- id: 2026-05-21-docs-full-audit
- fecha: 2026-05-21
- rama: develop
- skill: maturity_assessment + documentation
- fase: INVENTARIO + FUNCTIONAL + TECHNICAL + EXAMPLES + SYNC + REVIEW

## Prompt issued

Revisa el proyecto completo y actualiza la documentación pública en 6 fases:
1. Inventariar módulos reales en src/util_bbdd/ y clasificarlos.
2. Mapeo funcional con functional_doc.prompt.md por módulo sin doc o desactualizado.
3. Documentación técnica con technical_doc.prompt.md y Mermaid apropiado.
4. Ejemplos verificables en docs/examples/ para módulos sin ejemplo reproducible.
5. Sincronizar mkdocs.yml.
6. Revisión final: Markdown, enlaces y Mermaid; recomendar mkdocs build.
No inventes módulos ni capacidades. No uses APIs externas por ahora.

## Context supplied

- `src/util_bbdd/migrate/__init__.py` — docstring con todos los flujos soportados (12 combinaciones)
- `src/util_bbdd/migrate/planner.py` — parámetros completos por target
- `src/util_bbdd/migrate/transformers/oracle_to_{mariadb,sqlserver,postgresql}.py`
- `src/util_bbdd/migrate/transformers/mariadb_to_{oracle,sqlserver,postgresql}.py`
- `src/util_bbdd/migrate/emitters/{mariadb,oracle,sqlserver,postgresql}.py`
- Documentación pre-sesión en `docs/functional/`, `docs/api/`, `docs/examples/`
- `mkdocs.yml` — nav pre-sesión

## AI output summary

### FASE 1 — Inventario
- Mapeados todos los módulos en `src/util_bbdd/` vs docs existentes
- Hallazgos críticos: `migrate-oracle-mariadb.md` desactualizado (decía "Solo soporta Oracle como origen y MariaDB como destino"); sin doc para MariaDB como fuente; `DOCUMENTATION_STANDARD.md §4.2` con módulos de otro proyecto; `SHARED_INSTRUCTIONS.md` sin MySQL/Redshift/Snowflake
- Módulos bien documentados confirmados: managers, bulk, comparar, doc, metadata, query, validators, analysis, connection/factory

### FASE 2 — Documentación funcional
- Actualizado `docs/functional/migrate-oracle-mariadb.md`: tabla de parámetros por destino, diagrama sequenceDiagram genérico, ejemplos con tabs para 3 destinos, reglas de negocio ampliadas (ROWID, truncado por motor), límites y exclusiones corregidos
- Creado `docs/functional/migrate-mariadb-source.md`: objetivo de negocio, precondiciones con tabla por destino, sequenceDiagram Mermaid, reglas críticas (AUTO_INCREMENT→SEQUENCE+TRIGGER/IDENTITY/SERIAL; vistas pass-through), ejemplos para 3 destinos

### FASE 3 — Documentación técnica
- Actualizado `docs/api/migrate-oracle-mariadb.md`: flowchart TD con los 3 transformer-emitter paths, API pública completa incluyendo `OracleToSQLServerTransformer`, `OracleToPostgreSQLTransformer`, `SQLServerDDLEmitter`, `PostgreSQLDDLEmitter`; contratos de entrada expandidos con todos los parámetros por target; sección errores actualizada
- Creado `docs/api/migrate-mariadb-source.md`: misma estructura; nota admonition sobre charset/collation ignorados en MariaDB-como-fuente; flowchart TD completo con 3 paths

### FASE 4 — Ejemplos
- Actualizado `docs/examples/migrate-oracle-mariadb.md`: 3 secciones (Oracle→MariaDB, Oracle→SQL Server, Oracle→PostgreSQL) con extractos DDL representativos por motor; reporte Markdown; notas de operación generalizadas
- Creado `docs/examples/migrate-mariadb-source.md`: 3 secciones (MariaDB→Oracle, MariaDB→SQL Server, MariaDB→PostgreSQL) con extractos DDL; sección inspección de avisos; notas sobre AUTO_INCREMENT y vistas

### FASE 5 — Sincronización
- `mkdocs.yml` nav Funcional: renombradas entradas Oracle/SQL Server/PostgreSQL a "(origen)"; añadida entrada MariaDB (origen) → `functional/migrate-mariadb-source.md`
- `mkdocs.yml` nav Referencia Técnica: añadida entrada `api/migrate-mariadb-source.md`
- `mkdocs.yml` nav Ejemplos: añadida entrada `examples/migrate-mariadb-source.md`
- `mkdocs.yml` site_description: actualizada con migración DDL y todos los motores (MySQL/Redshift/Snowflake incluidos)
- `.github/DOCUMENTATION_STANDARD.md §4.2`: reemplazado nav de proyecto-copia erróneo por nav real de util_bbdd con todos los grupos
- `.github/SHARED_INSTRUCTIONS.md`: lista de motores ampliada (MySQL, Redshift, Snowflake añadidos); capacidades principales → migración DDL añadida como ítem explícito

### FASE 6 — Revisión final
- Verificado: 72 ficheros del nav existen en disco — 0 ausentes
- Verificado: textos estale eliminados (no hay "Solo soporta Oracle como origen y MariaDB como destino")
- Verificado: bloques Mermaid presentes y con tipo correcto en 4 documentos
- Ficheros nuevos/actualizados: 6 docs + mkdocs.yml + 2 ficheros de instrucciones IA

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Doc funcional Oracle (origen) | `docs/functional/migrate-oracle-mariadb.md` | actualizado |
| Doc funcional MariaDB (origen) | `docs/functional/migrate-mariadb-source.md` | creado |
| Doc técnica Oracle (origen) | `docs/api/migrate-oracle-mariadb.md` | actualizado |
| Doc técnica MariaDB (origen) | `docs/api/migrate-mariadb-source.md` | creado |
| Ejemplo Oracle (origen) | `docs/examples/migrate-oracle-mariadb.md` | actualizado |
| Ejemplo MariaDB (origen) | `docs/examples/migrate-mariadb-source.md` | creado |
| Nav funcional + API + ejemplos | `mkdocs.yml` | actualizado |
| Site description | `mkdocs.yml` | actualizado |
| Nav referencia §4.2 | `.github/DOCUMENTATION_STANDARD.md` | corregido |
| Motores + capacidades | `.github/SHARED_INSTRUCTIONS.md` | actualizado |

## Veredicto final

Veredicto: CLOSED
Pendientes al cierre:
- Ejecutar `mkdocs build` localmente para validar el build completo y los tabs de código (`pymdownx.tabbed`)
- Documentación de `results/` y `core/capabilities.py` no abordada (baja prioridad, uso interno)
