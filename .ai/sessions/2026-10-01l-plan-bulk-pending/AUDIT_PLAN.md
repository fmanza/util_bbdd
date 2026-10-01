# AUDIT_PLAN — pendientes de `bulk` tras v0.25.1

Revisión de `PLAN.md` contra el código (`e2ce535`) y mediciones de CPU sin servidor (2026-10-01).

**Veredicto: GO_CONDICIONAL**

| Punto | Veredicto | Condición |
|---|---|---|
| P-1 Filtro por columna | **GO** | Equivalencia exacta con `_fits` (test de propiedad) |
| S-4 Prefetch | **GO** (solo medición) | — |
| S-3 `ClientRead` | **GO** (solo diagnóstico) | D-1: herramienta de muestreo |
| S-2 Aislamiento de filas | **GO para el spike**; implementación tras su informe | D-2: datos de usuario en el CSV de rechazos |
| S-1 Procesos | **GO solo para el spike fuera de `src/`**; NO_GO para implementar hasta resolver R-5…R-7 | D-3 |

## Supuestos verificados

| # | Supuesto | Verificación | Resultado |
|---|---|---|---|
| V-1 | El filtro por valor es el coste del hotfix | CPU de `_openjson_payload`, 1M claves en lotes de 20 000 (mediana de 3): `INT` 0,40 s, `VARCHAR(10)` 0,31 s, `NUMERIC(12,2)` **2,06 s** | Confirmado; con PK `DECIMAL` es el caso dominante (no medido en el banco, que usa PK entera) |
| V-2 | Por columna es mucho más barato | Prototipo `INT` (`min`/`max` + `json.dumps`): 0,04 s | 10× |
| V-3 | `values` llegan como objetos Python | `batch_df[col].tolist()` (`delete_strategies.py`): `int64` → `int`, `object` → los objetos tal cual | Las comprobaciones agregadas operan sobre listas Python; `bool` sigue distinguible por tipo |
| V-4 | La auditoría CSV es segura entre procesos | `bulk/_audit/repository.py:31` `_get_file_lock` → `threading.Lock` por ruta | **No**: solo entre hilos (R-6) |
| V-5 | Los lectores son serializables | `range_partitioner.py:25,32,157` y la guía usan `lambda` como lector | **No** con `spawn` (Windows) (R-5) |
| V-6 | `py-spy` disponible para S-3 | `find_spec("py_spy")` y `PATH` | **No** (D-1) |

## Riesgos y condiciones

### P-1
- **R-1 Equivalencia**: el filtro decide qué claves van por OPENJSON; una divergencia con `_fits` reabriría el bug A1.
  Condición: test de propiedad que compare `_column_fits` con `all(_fits(...))` en miles de listas aleatorias por tipo
  (incluidos los bordes exactos de cada rango y longitud) **y** conservar intactos los 27 tests de dominio y los 6 de
  integración del hotfix.
- **R-2 `Decimal` con ceros a la derecha**: `Decimal("1.100")` tiene exponente −3 y cabe en escala 2. La vía rápida
  (`exponent >= -scale`) lo rechazaría: esos valores deben pasar por la comprobación exacta (`quantize`) en lugar de
  descartarse, o se perderían lotes válidos (solo rendimiento, no corrección). Cubierto por el test de propiedad.
- **R-3 Tipos mezclados**: una columna `object` con `int` y `str` debe rechazarse entera (hoy lo hace `_fits` valor a
  valor). `set(map(type, values))` lo detecta antes de agregar.

### S-2
- **R-4 Transacción abortada**: en PostgreSQL un error aborta la transacción; la bisección exige un SAVEPOINT por
  intento (`connection.begin_nested()`), en todos los motores para no ramificar. A verificar en el spike: COPY y el
  staging de UPDATE dentro de un SAVEPOINT (MySQL: `CREATE TEMPORARY TABLE` no hace commit implícito; comprobar que el
  rollback al SAVEPOINT no deja la temporal) y el coste de los SAVEPOINT por lote en PostgreSQL y SQL Server.
- La bisección solo es correcta si las filas del lote son independientes; filas con la misma PK dentro del lote cambian
  el resultado según el orden (UPDATE: gana la última). Documentar.

### S-1
- **R-5 Lectores no serializables** (V-5): con procesos hace falta otra forma de describir la partición (p. ej.
  `(sql, params)` o un *reader factory* importable). Cambio de API, no un parámetro más.
- **R-6 Auditoría entre procesos** (V-4): el `threading.Lock` no protege el CSV entre procesos; haría falta un lock de
  fichero (`msvcrt`/`fcntl`) o un CSV por proceso fusionado al final. Sin esto, la auditoría se corrompe.
- **R-7 Credenciales**: cada proceso necesita un engine nuevo; la URL con contraseña viajaría serializada al proceso
  (no por línea de comandos). Aceptable, pero nunca debe registrarse; preferir pasar el `URL` de SQLAlchemy y recrear el
  engine con los mismos `connect_args`.
- Coste de arranque en Windows (`spawn`): importar pandas/SQLAlchemy por proceso (~1–2 s): medir en el spike.

### S-3 / S-4
- Sin cambios en `src/`. S-4 solo repite E3 (3 repeticiones). S-3 usa muestreo con `sys._current_frames()`; el
  muestreador comparte el GIL con los hilos medidos, así que perturba algo la medida: comparar siempre 1 hilo frente a 4
  con el mismo muestreador.

## Orden confirmado
P-1 → S-4 → S-3 → S-2 → S-1 (igual que el PLAN). P-1 es independiente; S-3 puede cambiar la prioridad de S-1 (si la
causa es corregible con hilos, S-1 pierde interés).

## Decisiones para el usuario
- **D-1 (S-3)**: ¿muestreo con la biblioteca estándar (sin instalar nada; algo menos preciso) o instalar `py-spy` en el
  entorno de desarrollo? Recomendado: biblioteca estándar.
- **D-2 (S-2)**: el CSV de rechazos contendría filas de datos del usuario. ¿Solo opt-in con ruta explícita y sin
  escribirlo por defecto? Recomendado: sí (`rejects_csv_path` obligatorio con `on_error="isolate"`).
- **D-3 (S-1)**: ¿invertir en el spike de procesos sabiendo que implementarlo exige API nueva para los lectores y un
  lock de fichero para la auditoría? Recomendado: hacer primero S-3 y decidir con su resultado.
