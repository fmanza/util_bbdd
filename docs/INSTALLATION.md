# Guía de Instalación — util_bbdd

## 1. Requisitos Previos

- **Python 3.12+**
- `pip` actualizado: `pip install --upgrade pip`
- Acceso a red para instalar desde PyPI
- Driver Python del motor de base de datos que vayas a usar (ver [Paso 3](#3-drivers-por-motor))
- **Dependencia interna `util`**: `util_bbdd` depende de `util @ git+https://github.com/fmanza/util.git@develop` (timing automático), por lo que la instalación requiere acceso a GitHub salvo que se instale `util` por separado (ver [Solución de Problemas](#5-solucion-de-problemas))

## 2. Instalación del Paquete

### Instalación básica

```bash
pip install util_bbdd
```

### Extras opcionales

Solo estos extras están declarados en `pyproject.toml`:

| Extra | Comando | Para qué |
|---|---|---|
| `analysis` | `pip install "util-bbdd[analysis]"` | Grafos de relaciones entre tablas (Graphviz) |
| `doc-svg` | `pip install "util-bbdd[doc-svg]"` | Render de SVG a otros formatos (CairoSVG) |
| `docs` | `pip install "util-bbdd[docs]"` | Construir el sitio de documentación (MkDocs Material + mkdocstrings) |
| `dev` | `pip install "util-bbdd[dev]"` | Toolchain de desarrollo (pytest, ruff, mypy, build) |

!!! note
    La generación de documentación de BD (Word, Excel, HTML/Jinja2) **no requiere extra**: `openpyxl`, `python-docx` y `jinja2` forman parte de las dependencias base.

### Modo desarrollo (contribuidores)

```bash
git clone https://github.com/fmanza/util_bbdd.git
cd util_bbdd
python -m venv venv
# Windows:    .\venv\Scripts\Activate.ps1
# Linux/Mac:  source venv/bin/activate
pip install -e ".[dev]"
```

## 3. Drivers por Motor

Los drivers de base de datos **no se incluyen** en `util_bbdd`; instálalos por separado según el motor:

| Motor | Driver sync | Driver async | Comando de instalación |
|---|---|---|---|
| PostgreSQL | `psycopg2-binary` | `asyncpg` | `pip install psycopg2-binary asyncpg` |
| MariaDB / MySQL | `pymysql` | `aiomysql` | `pip install pymysql aiomysql` |
| SQLite | `sqlite3` (stdlib) | `aiosqlite` | `pip install aiosqlite` (sync incluido en Python) |
| Oracle | `oracledb` (incluido) | `oracledb` (incluido) | — (incluido en las dependencias base) |
| SQL Server | `pyodbc` | `aioodbc` | `pip install pyodbc aioodbc` + ODBC driver nativo del SO |
| HSQLDB | `jaydebeapi` | N/A (sin async) | `pip install jaydebeapi` + Java |

## 4. Verificación

Verificación sin servidor externo (SQLite en memoria):

```python
from util_bbdd import SyncDatabaseManager

with SyncDatabaseManager(db_type="sqlite", conn_params={"database": ":memory:"}) as mgr:
    mgr.execute_custom_many("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
    tablas = mgr.get_tables()
    print("Instalación correcta. Tablas:", [t["table_name"] for t in tablas])
    # → Instalación correcta. Tablas: ['test']
```

Verificación con un motor que requiere servidor (ejemplo PostgreSQL):

```bash
python -c "from util_bbdd import SyncDatabaseManager; m = SyncDatabaseManager('postgresql', {'host':'localhost','port':5432,'user':'postgres','password':'secret','database':'test'}); print('OK:', m.get_tables()); m.close()"
```

## 5. Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `No module named 'psycopg2'` | Driver PostgreSQL no instalado | `pip install psycopg2-binary` |
| `No module named 'pymysql'` | Driver MariaDB/MySQL no instalado | `pip install pymysql` |
| `pyodbc.Error: ('IM002'...)` | ODBC driver de SQL Server no instalado en el SO | Instalar [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| `oracledb.DatabaseError: DPY-2014` | Oracle Instant Client no encontrado | Descargar Oracle Instant Client y configurar `oracle_client_path` en `conn_params` |
| `pip install util_bbdd` falla resolviendo `util @ git+...` | Sin acceso a GitHub (CI offline, red corporativa) | `pip install git+https://github.com/fmanza/util.git@develop` y luego `pip install util_bbdd --no-deps` |
| `Timeout esperando conexión del pool` | Pool agotado | Aumentar `pool_size` en `conn_params`: `{"pool_size": 20, "max_overflow": 10, ...}` |
