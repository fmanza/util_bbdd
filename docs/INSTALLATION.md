# Guía de Instalación — util_bbdd

## 1. Objetivo

Instalar `util_bbdd` y el driver del motor de base de datos elegido, y verificar que la conexión funciona correctamente.

## 2. Requisitos Previos

- **Python 3.12+**
- `pip` actualizado: `pip install --upgrade pip`
- Acceso a red para instalar desde PyPI
- Driver Python del motor de base de datos que vayas a usar (ver Paso 2)

## 3. Pasos

### Paso 1 — Instalación básica

```bash
pip install util_bbdd
```

### Paso 2 — Instalar el driver del motor objetivo

Los drivers no están incluidos en `util_bbdd`; instálalos por separado según el motor:

| Motor | Driver sync | Driver async | Comando |
|---|---|---|---|
| PostgreSQL | `psycopg2-binary` | `asyncpg` | `pip install psycopg2-binary asyncpg` |
| MariaDB / MySQL | `pymysql` | `aiomysql` | `pip install pymysql aiomysql` |
| SQLite | `sqlite3` (stdlib) | `aiosqlite` | (incluido en Python) |
| Oracle | `oracledb` (incluido) | `oracledb` | — |
| SQL Server | `pyodbc` | `aioodbc` | `pip install pyodbc` + ODBC driver nativo |
| HSQLDB | `jaydebeapi` | N/A | `pip install jaydebeapi` + Java |

### Paso 3 — Extras opcionales

```bash
pip install "util-bbdd[doc]"       # Word, Excel, HTML docs
pip install "util-bbdd[analysis]"  # Grafos de relaciones (Graphviz)
```

### Paso 4 — Instalación en modo desarrollo (contribuidores)

```bash
git clone https://github.com/fmanza/util_bbdd.git
cd util_bbdd
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
# Linux/Mac: source venv/bin/activate
pip install -e ".[dev]"
```

### Dependencia interna: `util`

`util_bbdd` requiere `util @ git+https://github.com/fmanza/util.git@develop` para timing automático. Si `pip install util_bbdd` falla por falta de acceso a GitHub (CI offline, red corporativa):

```bash
pip install git+https://github.com/fmanza/util.git@develop
pip install util_bbdd --no-deps
```

## 4. Verificación

```python
from util_bbdd import SyncDatabaseManager

# SQLite no requiere servidor externo
with SyncDatabaseManager(db_type="sqlite", conn_params={"database": ":memory:"}) as mgr:
    mgr.execute_custom_many("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
    tablas = mgr.get_tables()
    print("Instalación correcta. Tablas:", [t["table_name"] for t in tablas])
    # → Instalación correcta. Tablas: ['test']
```

Para verificar con tu motor específico:

```bash
# PostgreSQL
python -c "from util_bbdd import SyncDatabaseManager; m = SyncDatabaseManager('postgresql', {'host':'localhost','port':5432,'user':'postgres','password':'secret','database':'test'}); print('OK:', m.get_tables()); m.close()"
```

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `No module named 'psycopg2'` | Driver PostgreSQL no instalado | `pip install psycopg2-binary` |
| `No module named 'pymysql'` | Driver MariaDB no instalado | `pip install pymysql` |
| `pyodbc.Error: ('IM002'...)` | ODBC driver de SQL Server no instalado en el SO | Instalar [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| `oracledb.DatabaseError: DPY-2014` | Oracle Instant Client no encontrado | Descargar Oracle Instant Client y configurar `oracle_client_path` en `conn_params` |
| `pip install util_bbdd` falla resolviendo `util @ git+...` | Sin acceso a GitHub | `pip install git+https://github.com/fmanza/util.git@develop` y luego `pip install util_bbdd --no-deps` |
| `Timeout esperando conexión del pool` | Pool agotado | Aumentar `pool_size` en `conn_params`: `{"pool_size": 20, "max_overflow": 10, ...}` |
