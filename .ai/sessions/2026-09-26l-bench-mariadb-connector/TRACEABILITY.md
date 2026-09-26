# TRACEABILITY

## Session metadata
- id: 2026-09-26l-bench-mariadb-connector
- fecha: 2026-09-26
- rama: develop (base `817007c`)
- skill: verificación + banco (sin cambios en `src/`)
- origen: petición del usuario: «Verifica que las pruebas para MariaDB se están realizando con su driver original» (ejemplo `mariadb+mariadbconnector`)

## Prompt issued
```
# Define the MariaDB engine using MariaDB Connector/Python
engine = sqlalchemy.create_engine("mariadb+mariadbconnector://…@127.0.0.1:3306/company")
Verifica que las pruebas para MariaDB se están realizando con su driver original.
```
(El ejemplo del usuario incluía credenciales de otro servidor; no se usaron ni se copiaron.)

## Verificación
- **No**: todas las pruebas y mediciones de MariaDB de las sesiones 2026-09-25/26 usaban **PyMySQL** (`mariadb+pymysql`): `scripts/bench_dump.py`, `scripts/bench_env.example.ps1`/`.sh` (URLs de tests de integración y del banco de `bulk`) y el campo `driver` de los resultados.
- MariaDB Connector/Python (`mariadb` 1.1.14) está instalado y previsto por el proyecto (override de mypy), pero ninguna medición lo usaba.
- Con Connector/Python, `bulk` escribe con otra estrategia: `MySQLMultiRowInsertStrategy` (con PyMySQL, `MySQLDriverExecutemanyStrategy`, P-02 de la auditoría de `bulk`).

## Cambios
- `scripts/bench_dump.py`: motor `mariadb_connector` (`mariadb+mariadbconnector`, mismo contenedor, datos y DDL que `mariadb`; `FAMILY` mapea DDL, datos, limpieza y verificación). `mariadb` sigue siendo PyMySQL.

## Mediciones (`results/`, `large`, 3,5M filas, 2 rondas intercaladas con PyMySQL)
- Conexión: módulo `mariadb.connections`, MariaDB 11.4.13; mismos 2M filas en `order_items`.
- **Fidelidad (round-trip de PD-05)** con Connector/Python: **exacto** (BIGINT ±(2^63−1) y 2^53+1 con NULL, DECIMAL(38,10) de 38 dígitos, cadenas con espacios).

| Driver | Variante | Total | `read` | `write` | RSS pico | Verificación |
|---|---|---|---|---|---|---|
| PyMySQL | `baseline` | 37,7 · 37,8 s | (con Q3, incluye espera en cola) | 26,3 · 27,1 s | 161 MB | 2/2 |
| Connector/Python | `baseline` | **77,3 · 79,7 s** | **4,7 · 5,9 s** | **69,9 · 71,9 s** | 192 MB | 2/2 |
| PyMySQL | `ranges4` | 69,0 · 71,7 s | — | — | 177 MB | 2/2 |
| Connector/Python | `ranges4` | 61,9 · 60,8 s | — | — | 205 MB | 2/2 |

- Connector/Python **lee 3–4 veces más rápido** (decodificación en C), pero el volcado es **el doble de lento**: la escritura con `MySQLMultiRowInsertStrategy` (construye `text()` multi-fila en Python) es el cuello.
- Q4 depende del driver: con Connector/Python, `ranges4` mejora un 22 % frente a su propia línea base (apoya la hipótesis del GIL con PyMySQL), aunque sigue por detrás de PyMySQL secuencial.
- **Microbanco de estrategia** (Connector/Python, 500K filas con tipos uniformes por columna, tabla `dump_dst.zz_mdbc` borrada al terminar): `MySQLMultiRowInsertStrategy` 10,49 s; `MySQLDriverExecutemanyStrategy` (envío masivo del driver) **2,82 s** (3,7×), mismos datos (COUNT y SUM iguales).

## Hallazgo nuevo (PF-09, pendiente de decisión)
- Con Connector/Python, `bulk` usa la vía multi-fila **a propósito**: el envío masivo del conector exige el mismo tipo Python por columna en todas las filas, y la normalización de `bulk` puede mezclarlos (`bytes`/`str` en un BLOB, `Decimal`/`float`) — documentado en `MySQLDriverExecutemanyStrategy`.
- Opción a valorar: usar el `executemany` del driver cuando las columnas del lote tengan tipo uniforme (el caso de `dump` tras PD-05, con los valores tal como los da el driver) y la vía multi-fila en otro caso. Es un cambio de diseño en `bulk` con riesgo de corrección: requiere su propio flujo.

## Directrices para Futuras IAs
- **[bench]**: `mariadb` en el banco es PyMySQL; para Connector/Python usa `mariadb_connector`. Los resultados de MariaDB de las sesiones anteriores son de PyMySQL.
- **[bulk/mariadb]**: con Connector/Python la escritura es el cuello (vía multi-fila); la lectura es mucho más rápida que con PyMySQL.

## Veredicto final
Veredicto: CLOSED (verificación). Pendiente: decisión sobre PF-09.
