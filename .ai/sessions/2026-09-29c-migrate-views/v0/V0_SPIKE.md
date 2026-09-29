# V0 — Spike de transpilado de vistas con sqlglot

- Fecha: 2026-09-29 · `sqlglot` 30.20.0 (sin dialecto MariaDB: se usa `mysql`) · banco: MySQL 8.4, MariaDB 11.4,
  PostgreSQL 17, SQL Server 2022, Oracle 23 Free.
- Script: `v0_spike_views.py` · resultados crudos: `results.json` (una entrada por vista y par).
- Método: mismas tablas y datos en los 5 motores (incluye un `NULL` y una cadena vacía); 31 construcciones comunes y 7
  específicas escritas en el dialecto nativo de cada origen; la definición se lee **del catálogo con los extractores
  de util_bbdd** (texto real que recibe `migrate`); normalización AST prevista para V1 (sin esquema en tablas y
  columnas; identificadores sin comillas y en minúsculas hacia MySQL/MariaDB); la vista se crea en el destino y su
  resultado se compara con el del origen.

## Resultado (31 construcciones comunes por par)

| Par | Se ejecuta | Mismo resultado |
|---|---|---|
| mariadb → mysql | 31/31 100 % | 31/31 100 % |
| mysql → mariadb | 31/31 100 % | 31/31 100 % |
| mysql/mariadb → postgresql | 29/31 94 % | 29/31 94 % |
| mysql/mariadb → sqlserver | 28/31 90 % | 28/31 90 % |
| mysql/mariadb → oracle | 28/31 90 % | 23/31 74 % |
| postgresql → mysql/mariadb | 31/31 100 % | 29/31 94 % |
| postgresql → sqlserver | 29/31 94 % | 29/31 94 % |
| **postgresql → oracle** | **23/31 74 %** | 21/31 68 % |
| sqlserver → mysql/mariadb | 31/31 100 % | 30/31 97 % |
| sqlserver → postgresql | 30/31 97 % | 30/31 97 % |
| sqlserver → oracle | 26/31 84 % | 22/31 71 % |
| oracle → mysql/mariadb | 31/31 100 % | 24/31 77 % |
| oracle → postgresql | 31/31 100 % | 26/31 84 % |
| oracle → sqlserver | 29/31 94 % | 24/31 77 % |

Umbral del plan (≥ 80 % del corpus común se ejecuta): **19 de 20 pares lo superan**; PostgreSQL → Oracle no (74 %).

## Causas de los fallos

### A. Artefactos del texto de catálogo (corregibles en el AST, deterministas)

| Causa | Construcciones / pares | Corrección prevista |
|---|---|---|
| PostgreSQL devuelve casts explícitos (`'Madrid'::text`, `::character varying`); `sqlglot` convierte `TEXT` en `CLOB` y `VARCHAR` sin longitud en `VARCHAR2` sin longitud para Oracle | c02, c07, c08, c09, c10, c11, c13, c27 (pg → oracle); c13 (sqlserver → oracle vía `LEN`) | Quitar casts redundantes a texto de literales/columnas; `TEXT`/`VARCHAR` sin longitud → `VARCHAR2(4000)` hacia Oracle |
| MySQL reescribe `CAST(x AS CHAR(10))` como `cast(x as char charset utf8mb4)` | c17 (mysql/mariadb → pg, sqlserver, oracle) | Quitar el charset del tipo del CAST |
| MySQL guarda `DATEDIFF` como `to_days(a) - to_days(b)`; `sqlglot` lo traduce con el origen `0000-01-01`, que PG y SQL Server rechazan | c16 (mysql/mariadb → pg, sqlserver, oracle) | `TO_DAYS(a) - TO_DAYS(b)` → diferencia de fechas del destino |
| `YEAR(x)` hacia Oracle queda como `YEAR(...)` | c14 (mysql/mariadb/sqlserver → oracle) | `YEAR/MONTH/DAY` → `EXTRACT(... FROM x)` hacia Oracle |

### B. Aritmética que depende del tipo (necesita los tipos de columna del plan)

| Caso | Pares | Efecto |
|---|---|---|
| `fecha + 30` (PostgreSQL/Oracle) → MySQL/MariaDB | pg/oracle → mysql/mariadb | **Se crea y da un número** (`20240140`): error **silencioso** |
| `fecha_a - fecha_b` (PostgreSQL/Oracle) → MySQL/MariaDB | idem | **Resultado erróneo silencioso** |
| `fecha + 30` / `fecha - fecha` → SQL Server | pg/oracle → sqlserver | Falla al crear (visible) |
| `DATE_ADD`/`INTERVAL` MySQL → SQL Server/Oracle | mysql/mariadb/sqlserver → sqlserver/oracle | Falla al crear |
| `a + b` de SQL Server con cadenas → PostgreSQL/Oracle | sqlserver → pg, oracle | Falla (PG) o error al consultar (Oracle) |

`sqlglot` puede anotar tipos (`annotate_types`) si recibe el esquema; el plan de `migrate` ya tiene los tipos de
todas las columnas, así que la corrección es viable. Sin ella, los casos silenciosos son el mayor riesgo del spike.

### C. Semántica del motor (no corregible; solo aviso)

- **Oracle: `''` es `NULL`.** Explica las diferencias de resultado de c08, c09, c23 y c29 en todos los pares con
  Oracle (la fila con `ciudad = ''`). Con datos sin cadenas vacías coinciden.
- **Concatenación con `NULL`.** Oracle `||` ignora el `NULL`; MySQL `CONCAT`, PostgreSQL `||` y SQL Server `+`
  devuelven `NULL` (c10 en los pares con Oracle y SQL Server → MySQL/MariaDB).

### D. Construcciones específicas

| Construcción | Resultado |
|---|---|
| `IF`/`IIF`/`DECODE` | 16/16 ok |
| `STRING_AGG`/`GROUP_CONCAT`/`LISTAGG` | 13/20 ok (falla hacia PostgreSQL sin cast a texto y desde PostgreSQL hacia MySQL) |
| `::text` de PostgreSQL | 3/4 (Oracle: `CLOB`, causa A) |
| `ILIKE` | 2/4 (SQL Server no lo tiene: `LOWER(x) LIKE LOWER(y)`) |
| `ROWNUM` | 0/4, falla al crear (visible) |
| `CONNECT BY` | 0/4, falla al crear (visible) |
| **Outer join `(+)` de Oracle** | 0/4: **se crea y devuelve otro resultado** (se convierte en join interno): error **silencioso** |

## Conclusión y decisión propuesta

1. El umbral se cumple en 19/20 pares solo con `sqlglot` + la normalización básica. Todas las causas de A son
   deterministas y pequeñas; con ellas, PostgreSQL → Oracle y el resto de pares con destino Oracle suben de forma
   previsible.
2. **El riesgo real no es lo que falla, sino lo que se crea y da otro resultado sin avisar** (B en MySQL/MariaDB y
   `(+)` de Oracle). V1 no debe activar `auto` sin estas **salvaguardas**:
   - anotación de tipos con el esquema del plan para la aritmética de fechas y la concatenación con `+`
     (corregir cuando se pueda; si no, *pass-through* con `WARNING`);
   - detección de `(+)`, `ROWNUM` y `CONNECT BY` en origen Oracle: *pass-through* con `WARNING` (o reescritura en V2);
   - aviso fijo de semántica en toda vista transpilada con origen o destino Oracle (`''` = `NULL`, concatenación).
3. Reordenar las entregas: **V1 = base + correcciones A + salvaguardas B/D**; V2 = reescrituras (`(+)` → `LEFT JOIN`,
   `ROWNUM` → `FETCH FIRST/LIMIT/TOP`, `ILIKE`, agregados de texto); V3 sin cambios.
