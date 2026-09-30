# Migración de vistas entre motores

## 1. Descripción General

Al migrar un schema con `MigrationPlanner`, el SQL de cada vista se reescribe al dialecto del motor destino: nombres
de tablas y columnas del plan, funciones equivalentes, sintaxis de límites de filas, aritmética de fechas y
construcciones propias del origen (outer join `(+)` de Oracle, `ROWNUM`, `ILIKE`, agregados de texto). Antes de
ejecutar el plan, las vistas se pueden validar contra el destino sin dejar cambios.

Cubre los 20 pares entre Oracle, MariaDB, MySQL, SQL Server y PostgreSQL. La reescritura usa
[sqlglot](https://github.com/tobymao/sqlglot), una dependencia opcional (`pip install "util_bbdd[migrate]"`); sin ella,
las vistas se copian sin reescribir, como hasta la versión 0.19.0.

**Precondiciones:**

- Las mismas que la migración DDL del motor origen (ver las páginas de cada origen en «Migración de Esquemas»)
- Para reescribir: sqlglot instalado (extra `util_bbdd[migrate]`)
- Para validar con destino PostgreSQL o SQL Server: conexión al servidor destino con permiso para crear tablas y
  vistas (se deshacen al terminar)

## 2. Reglas de Negocio

| Regla | Descripción | Impacto si se viola |
|---|---|---|
| Estrategia por defecto `"auto"` | Reescribe si sqlglot está instalado; si no, copia el SQL sin reescribir | Sin sqlglot, las vistas suelen fallar al crearse en otro motor |
| Nombres del plan | La vista usa los nombres de tablas, vistas y columnas del destino (mayúsculas en Oracle, truncados si hace falta) y pierde el prefijo del schema origen | Una vista que apunte al schema origen no existe en el destino |
| Aviso por vista reescrita | Cada vista reescrita lleva un aviso `INFO` «VIEW (reescrita)» para revisarla | — |
| Semántica de Oracle | Si el origen o el destino es Oracle, aviso `WARNING`: en Oracle la cadena vacía es `NULL` y `\|\|` ignora los `NULL` | La vista se crea, pero puede devolver otros datos con cadenas vacías o concatenaciones con `NULL` |
| Jerarquías de Oracle | `START WITH` + `CONNECT BY PRIOR a = b` sobre una sola tabla (con `AND LEVEL <= n` opcional en la condición, `LEVEL`, `SYS_CONNECT_BY_PATH` sobre texto variable o enteros, `CONNECT_BY_ROOT` y `CONNECT_BY_ISLEAF`) se convierte en una CTE recursiva; el `WHERE` se aplica **después** de recorrer la jerarquía, como en Oracle, y no convierte en hoja a un nodo cuyos hijos filtra. El generador `FROM dual CONNECT BY LEVEL <= n` también | Un filtro aplicado dentro de la jerarquía podaría las ramas bajo un nodo filtrado |
| `NOCYCLE` (solo destino PostgreSQL) | La CTE guarda en un array los valores de la columna de `PRIOR` del camino: no baja a una fila que ya está en él y `CONNECT_BY_ISLEAF` no cuenta ese hijo, como Oracle. Supone que esa columna identifica la fila (una clave). Con otro destino, la vista se copia sin reescribir | Sin `NOCYCLE`, un ciclo en los datos no termina o supera el límite de recursión |
| Límite de recursión y ciclos | Aviso `WARNING` «VIEW (jerarquía)»: SQL Server corta a 100 niveles y MySQL a 1000 (una vista no puede ampliarlo); en PostgreSQL y MariaDB un ciclo en los datos hace que la consulta no termine (salvo con `NOCYCLE` hacia PostgreSQL). El generador con más filas que ese límite se copia sin reescribir | Jerarquías profundas o datos con ciclos fallan al consultar la vista |
| Sin traducción fiable → sin reescribir | `CONNECT BY` fuera del subconjunto anterior, `ROWNUM` fuera de un límite de filas o SQL que sqlglot no entiende se copian tal cual con aviso `WARNING` «VIEW (sin reescribir)» | Hay que adaptar esa vista a mano |
| Referencias externas | Una vista que usa objetos fuera del schema migrado se reescribe con aviso `WARNING` «VIEW (referencia externa)» | El objeto referenciado debe existir en el destino |
| Validación sin cambios | En PostgreSQL y SQL Server se crean tablas y vistas en una transacción que se deshace; en MySQL, MariaDB y Oracle (el DDL confirma solo) se comprueba solo la sintaxis | Validar con DDL no transaccional dejaría objetos en el destino |

## 3. Casos de Uso

### Flujo principal

```mermaid
sequenceDiagram
    actor Dev as Desarrollador / DBA
    participant Plan as Planificador de Migración
    participant Rew as Reescritura de vistas
    participant Dst as Motor destino

    Dev->>Plan: Configurar (origen, destino, estrategia de vistas)
    Dev->>Plan: Planificar (conexión origen, schema)
    Plan->>Rew: SQL de cada vista + nombres y tipos del plan
    alt Traducción fiable
        Rew-->>Plan: SQL en el dialecto destino + aviso INFO
    else Construcción sin traducción
        Rew-->>Plan: SQL original + aviso WARNING
    end
    Dev->>Plan: Validar vistas (conexión destino)
    Plan->>Dst: Crear tablas y vistas en una transacción
    Dst-->>Plan: Error o éxito por vista (se deshace todo)
    Plan-->>Dev: Resultado por vista
    Dev->>Plan: Revisar avisos y ejecutar
    Plan->>Dst: DDL del plan
```

### Flujos alternativos

**Sin sqlglot:** con la estrategia `"auto"` las vistas se copian sin reescribir, con aviso de revisión; con
`"transpile"` el planificador falla al construirse y pide instalar el extra.

**Mantener el SQL original:** la estrategia `"passthrough"` copia siempre el SQL sin reescribir (comportamiento
hasta 0.19.0).

**Vistas de SQL Server con columnas en la cabecera** (`CREATE VIEW v (a, b) AS ...`): los nombres de la cabecera
pasan a ser alias de las columnas del `SELECT`.

**Límites y exclusiones:**

- No reescribe rutinas (procedimientos, funciones, triggers): siguen copiándose sin reescribir
- `CONNECT BY` solo se convierte en el subconjunto simple: `NOCYCLE` hacia un destino que no es PostgreSQL,
  `ORDER SIBLINGS BY`, joins en la consulta jerárquica, condiciones distintas de `PRIOR a = b` con `AND LEVEL <= n`
  (por ejemplo `AND activo = 1`), `CONNECT_BY_ISCYCLE`, `ROWNUM` y jerarquías dentro de subconsultas se copian sin
  reescribir, con el motivo en el aviso
- Sin `ORDER BY`, la vista convertida no conserva el orden en profundidad de Oracle (las filas son las mismas)
- La semántica de Oracle con cadenas vacías y `NULL` solo se avisa; no se corrige
- En MySQL, MariaDB y Oracle la validación es solo sintáctica: no detecta funciones o columnas inexistentes

## 4. Glosario y Términos

| Término | Definición |
|---|---|
| Reescritura (transpilado) | Traducción del SQL de una vista del dialecto del motor origen al del destino |
| Estrategia de vistas | Opción `view_strategy` del planificador: `"auto"`, `"transpile"` o `"passthrough"` |
| Pass-through | Copia del SQL original sin modificarlo, con aviso de revisión manual |
| DDL transaccional | Motores (PostgreSQL, SQL Server) en los que `CREATE TABLE`/`CREATE VIEW` se pueden deshacer con `ROLLBACK` |
| CTE recursiva | `WITH RECURSIVE` (`WITH` en SQL Server): una consulta ancla más otra que se une a la propia CTE, equivalente estándar de `CONNECT BY` |
| Top-N | Consulta que devuelve las N primeras filas según un orden (`LIMIT`, `TOP`, `FETCH FIRST`, `ROWNUM`) |
