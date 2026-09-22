---
applyTo: "src/**/*.py"
---
# Arquitectura OO, SOLID y Patrones

> **TL;DR** — 3 capas (Foundation → Core Services → Domain Logic). Separar extracción, normalización, render y persistencia (SRP). Extender por adaptadores/Strategy, nunca editando flujos base estables (OCP). Las implementaciones deben respetar contratos comunes (LSP). Orquestar desde Protocol/ABC, no desde clases concretas (DIP).

## Objetivo
Definir reglas de arquitectura para una librería multibase orientada a introspección, comparativas de esquemas y generación de documentación.

## Principios de diseño
- Claridad antes que abstracción: cada capa y cada clase deben tener un límite explícito.
- Evolución incremental: aplicar patrones solo cuando reducen acoplamiento o duplicación real.
- Compatibilidad: preservar API pública y contratos existentes salvo decisión explícita.

## Checklist SOLID para PR
- `SRP`: la clase/módulo tiene una razón de cambio dominante.
- `OCP`: agregar un motor/formato no requiere editar múltiples módulos estables.
- `LSP`: implementaciones concretas son intercambiables bajo el mismo contrato.
- `ISP`: contratos pequeños y orientados al uso; sin métodos no relevantes.
- `DIP`: capas de orquestación dependen de interfaces (`Protocol`/`ABC`), no de concretos.

## Patrones recomendados y uso
- `Strategy`: variaciones por motor o formato de salida.
- `Factory Method` / `Abstract Factory`: creación de adaptadores, conexiones y servicios por motor.
- `Adapter`: unificar diferencias entre drivers o APIs externas.
- `Template Method`: pipeline común con hooks por implementación.
- `Facade`: API de alto nivel para orquestar introspección, comparativa y render.
- `Builder`: construcción incremental de artefactos documentales.
- `Query Object` (Fowler): representar consultas de metadatos y aislar SQL.
- `Repository` (Fowler): acceso de lectura/escritura desacoplado de la capa de dominio.
- `Data Mapper` (Fowler): mapear filas/tablas a modelos de metadatos.
- `Identity Map` (Fowler): evitar cargas duplicadas dentro de una unidad de trabajo.

### Logging como responsabilidad transversal

Logging no es un patrón sino una responsabilidad **transversal** presente en todas las capas:

#### Principio SOLID aplicado
- **SRP**: Cada clase es responsable de su propio logging (rastreo de su estado y transiciones)
- **OCP**: Nueva clase → nuevo logger, sin modificar logging central
- **DIP**: Código de negocio NO depende de implementación de logging (delegar al `logging` module estándar)

#### Patrón en capas

**Level 1 (Foundation):** Clases contractuales, logging mínimo (protocolos/ABC)
```python
# _core/contracts.py
import logging

class ConnectionProvider(Protocol):
    """Contrato para proveedores de conexión."""
    def get_connection(self) -> Any: ...
```

**Level 2 (Services):** Clases que implementan servicios, logging obligatorio
```python
# connection/factory.py
import logging

logger: logging.Logger = logging.getLogger(__name__)

class ConnectionFactory:
    def create_connection(self, db_type: str) -> Connection:
        logger.info(f"Creating connection for {db_type}")
        try:
            conn = self._build_connection(db_type)
            logger.info(f"✅ Connection created: {conn}")
            return conn
        except Exception as e:
            logger.error(f"❌ Failed to create connection: {e}", exc_info=True)
            raise
```

**Level 3 (Specialization):** Clases que orquestan servicios, logging enriquecido con contexto
```python
# comparar/comparator.py
import logging

logger: logging.Logger = logging.getLogger(__name__)

class SchemaComparator:
    def __init__(self, ...):
        self.logger: logging.Logger = logging.getLogger(__name__)

    def compare_schemas(self, schema1: str, schema2: str) -> SchemaDiff:
        self.logger.info(f"Comparing {schema1} vs {schema2}")
        ...
```

#### Checklist arquitectónico con logging
- [ ] Cada clase con estado tiene `self.logger: logging.Logger` o módulo tiene `logger: logging.Logger`
- [ ] Logger inicializado en `__init__()`, `__post_init__()` (dataclass) o a nivel de módulo
- [ ] Métodos que mutan estado loguean transiciones (`self.logger.info()`)
- [ ] Métodos que fallan loguean con `self.logger.error(..., exc_info=True)`
- [ ] Métodos críticos loguean entrada/salida con `self.logger.debug()`
- [ ] Sin variables globales mutables (usar inyección o factory pattern)

## Anti-patrones
- `God class`.
- Condicionales por motor repartidos por toda la base de código.
- Mezclar lógica de negocio con detalles de render o transporte.
- Patrones aplicados por inercia sin necesidad demostrable.

## Reglas de acceso a metadatos (metadata access)

> Aplican a cualquier módulo de `src/util_bbdd/` que necesite metadatos de esquema.

### REGLA #1 — PUNTO Único DE ACCESO A METADATOS
`metadata/` es el único módulo autorizado para contener SQL de introspección de
esquemas y sus funciones `fetch_*_sql()`. NINGÚN otro módulo (`migrate`, `doc`,
`comparar`, `bulk`, etc.) puede definir sus propias queries SQL para obtener
tablas, columnas, índices, PKs, FKs o vistas.

- Si necesitas SQL de introspección, importa desde `metadata/<motor>/tables.py`.
- Si la query que necesitas no existe en `metadata/`, AÑÁDELA AHÍ primero y luego
  impórtala desde el módulo consumidor.
- El extractor de Oracle en `migrate/extractors/oracle.py` es el patrón canónico
  a seguir.

### REGLA #2 — CONSUMIR `SyncMetadataProvider`, NO EL MANAGER DIRECTAMENTE
Cuando un módulo de alto nivel (`doc`, `migrate`, `análisis`) necesite metadatos:
1. Recibe un objeto que satisface `SyncMetadataProvider` (o `AsyncMetadataProvider`).
2. Llama sus métodos (`get_tables()`, `get_columns(tabla)`, etc.).
3. NUNCA instancia un `SyncDatabaseManager` internamente ni ejecuta SQL propio.

Excepción explícita: `comparar/` usa SQLAlchemy Inspector porque su caso de uso
(comparar dos engines externos vía `sqlalchemy.engine`) es estructuralmente diferente
al acceso via manager. Esta excepción debe estar documentada en el módulo.

### REGLA #3 — PROHIBIDO DUPLICAR SQL DE INTROSPECCIÓN
Antes de escribir una query SQL que obtenga tablas, columnas, índices, FKs o PKs:
1. Busca en `metadata/<motor>/tables.py` y `metadata/<motor>/indexes.py`.
2. Si existe → impórtala. NO la copies.
3. Si no existe → créala en `metadata/<motor>/`, no en el módulo consumidor.
4. En auditoría (AUDIT_CODE): falla la revisión si `INFORMATION_SCHEMA`,
   `all_tables` o `all_tab_columns` aparecen en `migrate/`, `doc/` o `comparar/`
   fuera de `metadata/`.

### REGLA #4 — CONTRATOS ANTES QUE IMPLEMENTACIONES
Si un módulo nuevo necesita metadatos de BD:
- Define el Port/Protocol en `application/ports.py` o `contracts.py` del módulo.
- Implementa el adaptador en `infrastructure/adapters/`.
- Inyecta la dependencia por constructor.
- NUNCA importa directamente `SyncDatabaseManager` en la lógica de dominio.

### REGLA #5 — VALIDAR ANTES DE CREAR
Ante cualquier nueva clase, función o módulo que maneje metadatos de BD:
- Ejecuta `grep_search` en `src/util_bbdd/metadata/` buscando funcionalidad similar.
- Si existe → reutiliza. Si hay gap menor → extiende en `metadata/`. Si la lógica
  es nueva → crea en `metadata/` y expón en `metadata/__init__.py`.

### REGLA #6 — JERARQUÍA DE DEPENDENCIAS (capas estrictas)
La base de código se organiza en 3 niveles (Foundation, Core Services, Domain Logic), cada uno
dividido en capas numeradas. Un paquete importa **solo de paquetes de capas de número menor**;
los paquetes de una misma capa son independientes entre sí.

La tabla de capas es `LAYER` en `scripts/gen_arquitectura_capas.py` y se documenta en
`.ai/architecture.md` § Capas; las dos deben coincidir. Las capas se asignan por función, no por
la profundidad que tenga hoy el grafo de imports. `models.py` y `async_utils.py` son módulos raíz
de Foundation: no importan nada de la librería.

**Reglas explícitas:**
- Un import es válido solo si va a una capa de número menor. Ir a una capa superior o a la misma
  capa es una violación, aunque no cierre un ciclo (p. ej. `factory/` → `connection/` es válido;
  `results/` → `validators/`, ambos de la misma capa, no).
- Cada nivel agrupa capas consecutivas. En consecuencia: Level 2 **NUNCA** importa de Level 3 y
  Level 1 **NUNCA** importa de Level 2 ni Level 3.
- Los imports perezosos (dentro de una función) cuentan igual que los de módulo: aplazar un import
  no rompe un ciclo. Los imports bajo `TYPE_CHECKING` no crean ciclo en ejecución, pero tampoco
  pueden ir a una capa igual o superior.
- `__init__.py` de cada módulo solo re-exporta; no contiene lógica que genere ciclos.
- Un paquete nuevo necesita capa: añádelo a `LAYER` y a la tabla de `.ai/architecture.md`.

**Guarda automática:** `tests/unit/test_architecture_import_rules.py` falla ante un ciclo entre
paquetes, un import que no vaya a una capa inferior, una tabla de capas incoherente o un paquete
sin capa. Excepción vigente y acotada: `metadata/` → `managers/` bajo `TYPE_CHECKING` (marca 1 de
`docs/architecture.md`).

**En auditoría (AUDIT_CODE):** rechaza cualquier import que no vaya a una capa de número menor
(p.ej. `query/` importando de `managers/`, `results/` importando de `validators/` —misma capa— o
`connection/` importando de `factory/`).

## Evidencia mínima en cambios arquitectónicos
- Justificación del patrón elegido y alternativa descartada.
- Contrato tipado (`Protocol`/`ABC`) y al menos una implementación.
- Tests de contrato (incluye sustitución de implementaciones).
- Riesgos de compatibilidad y estrategia de rollback documentados.

## Referencias
- `G:\Mi unidad\Trabajo\Manuales\Desarrollo\Patrones de Diseño\design-patterns-es.pdf`
- https://martinfowler.com/eaaCatalog/
