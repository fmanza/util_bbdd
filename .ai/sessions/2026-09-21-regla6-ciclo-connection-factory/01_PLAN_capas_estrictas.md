# PLAN + AUDIT_PLAN — capas estrictas (pasos 1, 2 y 3)

Estado: **emitido, sin IMPLEMENT**. Formato `/refactor`. Veredicto: **GO_CONDICIONAL**.

## PLAN

**Objetivo.** Sustituir «3 niveles + acíclico dentro del nivel» por capas estrictas, sin cambiar comportamiento:
1. Tabla única de capas y guarda estricta (solo se importa hacia capas estrictamente inferiores).
2. Eliminar la única excepción `metadata → managers` (marca 1).
3. Que `analysis/` y `doc/` dependan de contratos y no de `managers/` (marca 2).

**API pública.** Solo cambia la anotación de 7 parámetros de constructor (2 en `metadata`, 3 en `analysis`, 2 en `doc`). Es una ampliación: siguen aceptando el manager concreto y cualquier objeto que cumpla el contrato.

**Precondición.** Cumplida el 2026-09-22: el trabajo previo quedó en el commit `92e6c7c`. Como las entradas de DECISIONS_LOG y CHANGELOG ya están commiteadas, el paso 1 las corrige en un commit nuevo.

### Tabla de capas (propuesta por función, no por profundidad accidental)

| Capa | Paquetes | Nivel |
|---|---|---|
| 1 | `_core`, `core`, `models`, `async_utils` | N1 |
| 2 | `_drivers` | N1 |
| 3 | `results`, `validators` | N2 |
| 4 | `connection`, `query` | N2 |
| 5 | `executors`, `factory`, `metadata` | N2 |
| 6 | `bulk`, `comparar`, `migrate`, `managers` | N3 |
| 7 | `analysis`, `dump` | N3 |
| 8 | `doc` | N3 |

Estado final tras el paso 3: `analysis` baja a la capa 6 y `doc` a la 7 (7 capas). **Orden de operaciones:** primero se quitan los imports de `managers`, después se bajan las capas; al revés, la guarda falla con `analysis → managers`.

### Pasos

| Paso | Rutas | Cambio |
|---|---|---|
| 1 | `scripts/gen_arquitectura_capas.py`, `tests/unit/test_architecture_import_rules.py`, docs | `LAYER` como fuente única; `LEVEL` derivado (1-2 → N1, 3-5 → N2, 6-8 → N3); la guarda pasa a `test_imports_only_go_to_lower_layers`; tests de capas contiguas y niveles no decrecientes; tabla de capas solo en el script y en `.ai/architecture.md` (el resto enlaza); corregir la frase «sin ganar nada» de DECISIONS_LOG y CHANGELOG |
| 2 | `metadata/adapters/base_adapter.py`, `metadata/adapters/_adapter_protocol.py` | Protocol `MetadataCachePort` (`clear_all`, `clear_table`, `clear_routine`, `clear_context`); sustituye el import `TYPE_CHECKING` (l. 17) y las anotaciones (l. 29 y 160); `TYPING_ONLY_UPWARD` queda vacío; test de conformidad con `CacheService` real |
| 3 | `analysis/` (3 ficheros), `doc/` (2 ficheros) | `analysis/contracts.py` con `RelationshipGraphSource`; `DocumentationSourcePort` en `doc/application/ports.py` compuesto de puertos existentes; quitar imports de `managers`; bajar capas; figura, `docs/api/analysis.md` (diagrama Mermaid) y `docs/api/database-documentation.md` |

## Datos medidos (grafo real, 338 ficheros)

| Esquema | Capas | Imports horizontales (runtime) | Ascendentes |
|---|---|---|---|
| Niveles de `architecture.instructions.md` (antes de reconciliar) | 3 | 17 | ciclo horizontal `managers ⇄ metadata` (solo tipado) |
| Niveles de `.ai/architecture.md` (adoptados) | 3 | 11, ninguno bidireccional | 1, solo tipado (`metadata → managers`) |
| Capas finas (tabla de arriba) | 8 | 0 | 1, solo tipado |

- Tabla del paso 1: 0 violaciones en runtime y 1 de tipado (la excepción). Paso 2: 0. Paso 3: 0 con la tabla de 8 y con la de 7 capas. Los niveles derivados coinciden siempre con `.ai/architecture.md`.
- Estratos mínimos: 7 hoy; 5 si `analysis` y `doc` no importaran `managers`. 26 de 38 aristas de runtime saltan capas (permitido).
- Lo que «niveles + acíclico» deja pasar y las capas estrictas no: `results → connection` y `connection → query` (mismo nivel, sin ciclo).

## Hechos que condicionan el diseño

- **Marca 1.** `metadata/adapters/base_adapter.py:17` importa `CacheService` bajo `TYPE_CHECKING` solo para anotar `cache_service` (l. 29 y 160); no hay ningún `self.cache.<atributo>` en todo `metadata/`. `_adapter_protocol.py` menciona `CacheService` solo en un docstring. `CacheService` arrastra `CacheManager` y `CacheKeyFactory` (módulos privados de `managers/`): moverlo no es barato.
- **Marca 2, `analysis/`.** Importa el manager en `base.py:16` (l. 131-132), `graphviz_ext.py:23` (l. 61) y `matplotlib_graph.py:14` (l. 45) solo como anotación. Usa `db_type`, `get_tables`, `get_columns`, `get_primary_keys`, `get_foreign_keys`, `get_unique_constraints`, `get_query_context_database` y `relationship_cache` (10 métodos distintos de `set_/get_` cardinality, unique constraints, primary keys, is_unique_column, is_primary_key).
- **Marca 2, `doc/`.** Ya es hexagonal (`DocumentationManagerPort`). Solo `database_documentation.py:13` (l. 84) y `infrastructure/adapters/sync_database_manager_adapter.py:9` (l. 25) nombran el manager concreto; el adaptador delega unos 24 miembros.
- **Hueco de tipado.** `doc` pasa a `analysis` su adaptador (`DocumentationManagerPort`), no un `SyncDatabaseManager`, y lo tapa con un `cast` en `documentation_orchestrator.py:558`. El puerto no declara `relationship_cache`.
- **`SyncMetadataProvider` no sirve** para sustituir el manager: cubre 9 lecturas, y sus parámetros se llaman `tabla`, incompatibles con los posicionales (`table_name, /`) del adaptador. `DbManagerProtocol` aparece solo en docstrings; no está definido.

## AUDIT_PLAN

**Funcionales.** Runtime idéntico (anotaciones y Protocols). `doc/database_documentation.py` no usa `from __future__ import annotations`: el Protocol debe importarse a nivel de módulo, no bajo `TYPE_CHECKING`. `runtime_checkable` con miembros no-método solo comprueba presencia, no firmas. Marca 1: el Protocol no puede derivarse del uso (no hay uso); reflejará la API pública de `CacheService`.

**Técnicos (LSP/ISP).** Protocols definidos por el consumidor, con parámetros posicionales (`/`) y `db_type` como `@property`; no extender `SyncMetadataProvider`. `analysis` necesita unos 8 miembros; `doc`, unos 24: componer con puertos existentes en vez de un Protocol monolítico. `mypy src` no ve la conformidad (los objetos se pasan en tests y hay un `cast`): verificar un fichero de conformidad con mypy en AUDIT_CODE. La tabla de capas es criterio: en la capa 6 conviven `bulk`, `comparar`, `migrate` y `managers`, y un import futuro entre ellos fallará por diseño. Seis documentos enuncian la regla: concentrar la tabla en dos sitios.

**Seguridad.** Sin riesgo funcional (sin SQL, credenciales ni parametrización). El subproceso de la guarda ejecuta código fijo con argumentos derivados de nombres de directorio del repo.

**Simplificaciones.** `relationship_cache` con la clase concreta `RelationshipMetadataCache`; no tocar `managers/`; mantener el `cast` del adaptador; figura con 3 bandas más tabla de capas en Markdown; sin import-linter; tras el paso 3, retirar del dibujo la leyenda y la flecha ámbar que dejen de usarse.

**Veredicto: GO_CONDICIONAL.** Decisiones abiertas del usuario:
1. Confirmar la tabla de capas, en especial la capa 6.
2. ¿`DocumentationManagerPort` gana `relationship_cache`? (recomendado: sí, cierra el hueco del `cast`).
3. ¿Se añade el fichero de conformidad al paso `mypy` de `.github/workflows/tests.yml`? (recomendado: sí; una línea, fuera de los tres pasos).
