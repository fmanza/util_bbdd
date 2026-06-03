# Volcado de Datos entre Esquemas

## 1. Descripción General

Copia todos los datos de un esquema/base de datos origen a un esquema/base de datos destino, respetando automáticamente el orden de carga impuesto por las claves foráneas, gestionando constraints por motor y generando un informe Excel de auditoría al finalizar.

Casos de uso típicos: refrescar un entorno de pruebas con datos de producción; migrar datos durante un cambio de motor (Oracle → SQL Server); sincronizar un esquema de réplica o analítica; restaurar un subconjunto de tablas desde un backup en vivo.

La carga sigue 7 fases automáticas: introspección → análisis topológico FK → desactivación de constraints → limpieza del destino (opcional) → carga best-effort en orden topológico → rehabilitación de constraints → generación de informe Excel.

**Precondiciones:**

| Requisito | Detalle |
|---|---|
| Engines activos | Ambos engines SQLAlchemy deben poder conectarse antes de iniciar el volcado |
| Esquemas existentes | Las tablas destino deben existir (el módulo no aplica DDL, solo datos) |
| Permisos de lectura | El usuario origen necesita SELECT sobre todas las tablas a volcar |
| Permisos de escritura | El usuario destino necesita INSERT, DELETE/TRUNCATE y permisos de gestión de constraints |
| Python 3.12+ | Requerido por `util_bbdd` |

## 2. Reglas de Negocio

| Regla | Descripción | Impacto si se viola |
|---|---|---|
| Solo datos, nunca DDL | Si una tabla existe en origen pero no en destino, se informa como `missing_target` y se omite | La tabla no se crea automáticamente en destino |
| Columnas faltantes se saltan | Si una columna existe en origen pero no en destino, se omite de la SELECT y se informa | No hay error; la columna se registra como omitida en el informe |
| Comparación case-insensitive | Nombres de tabla y columna se comparan sin distinguir mayúsculas/minúsculas entre motores | Necesario para interoperabilidad entre motores (PostgreSQL lowercase ↔ Oracle UPPERCASE) |
| Errores de tabla no detienen el volcado | Cada tabla es independiente; se registra el error y se continúa con la siguiente | Carga best-effort; validar integridad post-volcado |
| Rehabilitación de constraints siempre se ejecuta | El gestor de constraints actúa como context manager y garantiza la rehabilitación aunque la carga falle | Las constraints quedan activas incluso en caso de error parcial |
| Informe Excel siempre se genera | Se genera independientemente de si hubo errores parciales | El informe refleja el estado real de cada tabla, incluidos los errores |

## 3. Casos de Uso

### Flujo principal

```mermaid
flowchart TD
    A([Inicio]) --> B[Fase 1: Introspección\nde origen y destino]
    B --> C[Fase 2: Análisis topológico FK\nAlgoritmo de Kahn]
    C --> D[Fase 3: Desactivar constraints\nPor motor destino]
    D --> E{truncate_target?}
    E -- Sí --> F[Fase 4: Limpiar destino\nOrden inverso topológico]
    E -- No --> G
    F --> G[Fase 5: Carga best-effort\nOrden topológico]
    G --> H[Fase 6: Rehabilitar constraints\nSiempre ejecutada]
    H --> J{sync_pk_sequences?}
    J -- Sí --> K[Fase 6a: Sincronizar\ncontadores PK]
    J -- No --> I
    K --> I[Fase 7: Generar informe Excel]
    I --> Z([DumpResult])
```

### Flujos alternativos

**Tablas con ciclos FK:** Cuando dos o más tablas tienen claves foráneas circulares, el algoritmo las detecta, las carga al final sin garantía de orden (con constraints desactivadas) y las registra en el informe con indicador de ciclo FK.

**Volcado en modo append:** Con `truncate_target=False`, los datos se insertan sin limpiar el destino primero. Puede generar duplicados si los registros ya existen.

**Palancas de rendimiento opcionales:** Cuatro opciones opt-in permiten acelerar el volcado en escenarios de alto volumen: cadencia de commit, gestión de índices, paralelismo por tabla y paralelismo por rangos PK. Todas están desactivadas por defecto.

| Palanca | Parámetro | Efecto | Contrapartida |
|---|---|---|---|
| Cadencia de commit | `commit_every_n_chunks=N` | Commit cada N lotes; acota el undo log | La carga de la tabla deja de ser atómica |
| Gestión de índices | `manage_indexes=True` | Deshabilita índices secundarios durante la carga | DROP+recreate en PostgreSQL (destructivo) |
| Paralelismo por tabla | `max_parallel_tables=N` | Carga tablas independientes en paralelo | Solo dentro del mismo nivel topológico FK |
| Paralelismo por rangos PK | `parallel_pk_ranges=N` | Particiona una tabla con PK entera en N rangos | Requiere destino sin triggers per-fila |

**Límites y exclusiones:**

- Sin transacción global: cada tabla se inserta en su propia transacción
- Resincronización de secuencias/identidades: soportada para PostgreSQL, SQL Server, MariaDB y Oracle ≥ 12c
- Gestión de constraints solo en SQL Server, MariaDB, PostgreSQL y Oracle
- Paralelismo por rangos PK solo para tablas con PK de una única columna entera
- El informe Excel requiere `openpyxl` instalado

## 4. Glosario y Términos

| Término | Definición |
|---|---|
| Algoritmo de Kahn | Algoritmo de ordenamiento topológico que determina el orden de carga de tablas respetando las dependencias de clave foránea |
| Ciclo FK | Situación donde dos o más tablas tienen claves foráneas que se apuntan mutuamente, imposibilitando un orden de carga lineal |
| Carga best-effort | Estrategia donde un error en una tabla no detiene el volcado; las demás tablas se cargan igualmente |
| `truncate_target` | Opción que indica si las tablas destino deben vaciarse antes de la inserción de nuevos datos |
| `sync_pk_sequences` | Opción que actualiza los contadores de PK del destino (sequences, IDENTITY, AUTO_INCREMENT) tras la carga de datos con PKs explícitas |
