# PLAN + AUDIT_PLAN — EngineReadinessAdvisor.report_once(engine)

> **v2** (sustituye a la v1 de esta misma sesión). La v1 era un hotfix mínimo (`claim_first_report` + guarda
> en `crud.py`) que dejaba en `bulk/` el cálculo de `conn_params`. El usuario pidió explícitamente aplicar la
> recomendación completa: verificación única por engine **y** traslado de la lectura de URL/pool a
> `connection/`. Se combina hotfix + refactor acotado por petición expresa (SHARED § Flujo de trabajo).

## PLAN

### Objetivo
1. La verificación de condiciones de ejecución se hace **una sola vez por `Engine`** en el proceso,
   aunque se creen muchas `BulkCrud` sobre él y desde varios hilos.
2. `bulk/` deja de conocer detalles del pool (`pool.size()`, `pool._max_overflow`, `pool._timeout`) y de
   cómo se arman los `conn_params` del advisor: esa responsabilidad pasa a `connection/`.

### Causa raíz
- Disparador en `BulkCrud.__init__` → `__validate_engine_config()` (`src/util_bbdd/bulk/crud.py` l. 238 y
  299-343): por instancia hace `self.engine.connect()` (checkout del pool), lanza las consultas dinámicas
  y emite el informe. No hay memoria de «engine ya verificado».
- Varias `BulkCrud` por engine:

  | Punto | Frecuencia |
  |---|---|
  | `bulk/_execution/parallel_loader.py:394` `_load_partition` | 1 por partición (hilo) |
  | `bulk/_execution/parallel_loader.py:639` `_resolve_table` | 1 por `load()` |
  | `dump/orchestrator.py:752` `_make_worker_crud` (l. 200, 682, 712) | 1 por hilo/ciclo/principal |
  | `dump/orchestrator.py:558` `ParallelBulkLoader` | multiplica lo anterior por tabla |

- Síntoma: N informes idénticos y N checkouts extra que compiten con los workers (en MariaDB disparan
  además los listeners `checkout`/`checkin` de `dump/_constraints.py:168`).
- Causa de diseño: la verificación es propiedad del engine pero se modeló como paso de la instancia
  `BulkCrud`. F-04 de la sesión `2026-09-27-engine-readiness-advisor` asumió una sola instancia.

### Diseño

**`src/util_bbdd/connection/performance_advisor.py`**

```python
_reported_engines: ClassVar[weakref.WeakSet[Engine]] = weakref.WeakSet()
_reported_lock: ClassVar[threading.Lock] = threading.Lock()

def report_once(self, engine: Engine) -> bool:
    """Verifica ``engine`` y emite su informe solo la primera vez que se pide en el proceso.

    Thread-safe: el engine se registra antes de verificarlo, de modo que los hilos concurrentes
    no repiten la verificación ni esperan a que termine. Registro con referencias débiles.

    Returns:
        True si esta llamada hizo la verificación; False si el engine ya estaba verificado.
    """
    with self._reported_lock:
        if engine in self._reported_engines:
            return False
        self._reported_engines.add(engine)

    dialect = engine.dialect.name
    conn_params = self._conn_params_from_engine(engine)
    try:
        with engine.connect() as conn:
            self.report(dialect, conn_params, connection=conn)
    except Exception:
        # Sin conexión activa, solo checks estáticos
        try:
            self.report(dialect, conn_params)
        except Exception as exc:
            logger.debug(f"Error en verificación de motor '{dialect}': {exc}")
    return True

@staticmethod
def _conn_params_from_engine(engine: Engine) -> dict[str, Any]:
    """host/port/database de ``engine.url``, pool_size/max_overflow/pool_timeout del pool
    y, en mssql, el driver (pyodbc | pymssql)."""
```

- `_conn_params_from_engine` es el cuerpo actual de `crud.py:307-332` trasladado **sin cambios de
  semántica**, con una salvedad: el driver de SQL Server se deriva de `engine.url.drivername` en lugar de
  `BulkCrud.db_info`. Es equivalente: `db_info` contiene `pyodbc` solo si `drivername` lo contiene
  (`__detectar_sqlserver_driver`, crud.py:279-288), y en cualquier otro caso ambos dan `pymssql`.
  Así `report_once` no necesita parámetros de `bulk/`.
- `check()` y `report()` no cambian: la llamada explícita sigue verificando siempre (contrato D-02 intacto).
- Tipo `Engine` importado bajo `TYPE_CHECKING` (el módulo usa `from __future__ import annotations`).

**`src/util_bbdd/bulk/crud.py`**

```python
def __validate_engine_config(self) -> None:
    """Verifica las condiciones de ejecución del motor una vez por engine (ver ``EngineReadinessAdvisor.report_once``)."""
    EngineReadinessAdvisor().report_once(self.engine)
```

- Import en cabecera: `from ..connection.performance_advisor import EngineReadinessAdvisor`.
- Se elimina el `try/except ImportError` (código muerto: `connection/`, capa 4, siempre está disponible
  para `bulk/`, capa 6) y el bloque de `conn_params` (l. 307-343). Si `Any` deja de usarse, se retira del import.

**Docstrings**: módulo y clase de `performance_advisor.py` (uso típico con `report_once`; `report()`
explícito no está limitado; la clave es el objeto engine, no la URL).

### Tests

Nuevo `tests/unit/connection/test_performance_advisor_once.py` (`report_once` y `_conn_params_from_engine`
son de `connection/`):

| Test | Verifica |
|---|---|
| `report_once` → True y luego False sobre el mismo engine | contrato |
| 2 engines distintos → True/True y 2 informes | la clave es el objeto engine |
| Engine liberado (`del` + `gc.collect()`) desaparece del registro | sin fugas |
| 2.ª llamada → 0 checkouts (listener `checkout`) y 0 registros en `caplog` | no pide conexión ni escribe log |
| 8 hilos (`ThreadPoolExecutor` + `Barrier`) → exactamente 1 True y 1 informe | concurrencia |
| `engine.connect()` falla → informe solo estático, sin excepción, devuelve True | fallback |
| `_conn_params_from_engine`: SQLite en fichero con `pool_size=3, max_overflow=7, pool_timeout=12` | host/port/db + pool |
| `_conn_params_from_engine`: engine falso (`SimpleNamespace`) con `url=make_url("mssql+pyodbc://…")` y con `mssql+pymssql://…` | driver SQL Server sin drivers instalados |
| `_conn_params_from_engine`: pool sin `size()` ni atributos privados (`NullPool`) | degradación D-05 |

Nuevo `tests/unit/bulk/test_engine_readiness_once.py` (integración con `BulkCrud`):

| Test | Verifica |
|---|---|
| 5 `BulkCrud` sobre el mismo engine SQLite en fichero (`tmp_path`) → 1 `ENGINE READINESS REPORT` | síntoma principal |
| 8 hilos creando `BulkCrud` sobre el mismo engine → 1 informe | escenario `ParallelBulkLoader`/`dump` |

Cada test crea su propio engine: el registro compartido no acopla tests.

### Rutas afectadas
- `src/util_bbdd/connection/performance_advisor.py` — `report_once`, `_conn_params_from_engine`, 2 `ClassVar`, docstrings
- `src/util_bbdd/bulk/crud.py` — `__validate_engine_config` a 1 línea, import en cabecera
- `tests/unit/connection/test_performance_advisor_once.py` (nuevo)
- `tests/unit/bulk/test_engine_readiness_once.py` (nuevo)
- En VERSION: `CHANGELOG.md` (`[Unreleased]`: `### Fixed` + `### Changed`), `.ai/DECISIONS_LOG.md`,
  `.ai/sessions/INDEX.md`, `.ai/CURRENT_STATE.md`

### Fuera de alcance
- Parámetro `check_engine_readiness` en `BulkCrud`: innecesario con el registro por engine.
- Refactor de `MySQLVariableValidator` (F-07 de la sesión anterior).
- Comprobación única en `SyncDatabaseManager`/`AsyncDatabaseManager`: hoy no invocan el advisor.

### Dato faltante o supuesto
- **Supuesto**: la configuración del servidor no cambia en caliente de forma que merezca un nuevo informe
  automático; `report()` explícito sigue disponible.
- **Verificado**: `sqlalchemy.Engine` (2.0.50) y `MagicMock` admiten `weakref`.
- **Verificado**: ningún test referencia `__validate_engine_config`; solo
  `tests/unit/connection/test_performance_advisor.py` usa el advisor y llama a `report()` directamente.
- **Por verificar en IMPLEMENT**: que el import en cabecera de `crud.py` no cree ciclo de importación
  (`crud.py` ya importa `metadata/` en cabecera, capa superior a `connection/`; riesgo bajo). Si lo
  hubiera, se mantiene como import perezoso sin `try/except`.

---

## AUDIT_PLAN

### Riesgos funcionales
| # | Riesgo | Evaluación | Mitigación |
|---|---|---|---|
| RF-1 | Tras `engine.dispose()` no se vuelve a verificar | Correcto: mismo objeto, misma URL y pool | — |
| RF-2 | Dos `Engine` a la misma URL → 2 informes | Aceptable: pueden tener pool distinto; clave por URL daría falsos negativos | Docstring + test |
| RF-3 | Si la primera verificación no conecta, solo hay estáticos y no se reintenta | Comportamiento de fallback ya existente; reintentar reabriría el problema | Docstring + test |
| RF-4 | Cambio de parámetros del servidor en caliente sin nuevo informe | Supuesto aceptado | `report()` explícito |
| RF-5 | `report()`/`check()` explícitos quedan limitados | No: la unicidad solo está en `report_once` | Tests existentes intactos |
| RF-6 | Driver SQL Server derivado de `url.drivername` en vez de `db_info` | Equivalente en todos los casos (ver Diseño) | Test con pyodbc y pymssql |
| RF-7 | El mensaje debug de fallo pasa del logger `util_bbdd.bulk.crud` al de `util_bbdd.connection.performance_advisor` | Solo nivel DEBUG; el informe ya se emitía con el logger del advisor | — |

### Riesgos técnicos
| # | Riesgo | Evaluación |
|---|---|---|
| RT-1 | Carrera entre hilos | `Lock` + registro antes de verificar; test con `Barrier` y 8 hilos |
| RT-2 | Fuga de memoria | `WeakSet`; test con `gc.collect()` |
| RT-3 | Estado global mutable (SHARED § OOP) | Excepción justificada: la unicidad es de proceso; `ClassVar` débil y protegido. Se registra en `DECISIONS_LOG.md` |
| RT-4 | Aislamiento de tests | Engine propio por test; sin hook de reseteo |
| RT-5 | Engines `MagicMock` en tests de bulk | Admiten `weakref`; el camino de error (atributos `Mock` en `conn_params`) ya existía y está cubierto por el triple try/except |
| RT-6 | Regla #6 (capas) | `bulk/` (capa 6) → `connection/` (capa 4) ya existía; `connection/` no importa nada nuevo en ejecución (`Engine` solo bajo `TYPE_CHECKING`). `gen_arquitectura_capas.py` y `test_architecture_import_rules.py` no cambian |
| RT-7 | Ciclo de importación al subir el import a cabecera | Bajo; se verifica en IMPLEMENT con `pytest --collect-only` e `import util_bbdd` |
| RT-8 | Rendimiento | Mejora: elimina N-1 checkouts y N-1 tandas de consultas por carga |
| RT-9 | Atributos privados del pool (D-05) | Se trasladan sin cambios con `getattr(..., None)`; ahora aislados en `connection/`, el único que debe conocerlos |

### Riesgos de seguridad
- Ninguno nuevo. Menos consultas de diagnóstico; whitelists D-03 sin cambios. `conn_params` sigue sin
  incluir usuario ni contraseña (solo host/port/database/pool/driver), así que el informe no expone credenciales.

### API pública
- Aditiva: `EngineReadinessAdvisor.report_once(engine) -> bool`. Sin cambios en firmas existentes.
- `BulkCrud`: sin cambio de firma. Único cambio de comportamiento: un informe por engine en lugar de uno por instancia.
- Versión sugerida en VERSION: **0.18.2** (patch: fix + cambio interno compatible).

### Validación prevista en IMPLEMENT
```bash
python -c "import util_bbdd"
python -m ruff check src tests
python -m ruff format src tests
python -m mypy src tests/unit/test_protocol_conformance.py
python -m pytest tests/unit/connection tests/unit/bulk/test_engine_readiness_once.py -q
python -m pytest
python scripts/gen_arquitectura_capas.py --edges   # confirmar que no cambia ninguna arista
```

### Veredicto
**GO** — causa raíz verificada; 2 ficheros de `src` (uno reduce ~40 líneas, otro las recibe), API solo
aditiva, riesgos cubiertos por tests. Pendiente de aprobación del usuario para IMPLEMENT.
