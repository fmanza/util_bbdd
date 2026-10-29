# Guía de Instalación — util_bbdd

## 1. Requisitos Previos

- **Python 3.12+**
- `pip` actualizado: `pip install --upgrade pip`
- Acceso a GitHub: `util_bbdd` no está publicado en PyPI y se instala desde su repositorio
- Driver Python del motor de base de datos que vayas a usar (ver [Paso 3](#3-drivers-por-motor))

## 2. Instalación del Paquete

### Instalación básica

Desde el repositorio, fijando la versión con su tag:

```bash
pip install "util_bbdd @ git+https://github.com/fmanza/util_bbdd.git@v5.1.0"
```

### Extras opcionales

Extras declarados en `pyproject.toml` (se combinan: `util_bbdd[postgresql,analysis]`):

```bash
pip install "util_bbdd[postgresql] @ git+https://github.com/fmanza/util_bbdd.git@v5.1.0"
```

| Extra | Para qué |
|---|---|
| `postgresql` | Drivers PostgreSQL: `psycopg[binary]` + `psycopg-pool` (sync) y `asyncpg` (async) |
| `mariadb` | Drivers MariaDB: `mariadb` (MariaDB Connector/Python, sync) y `aiomysql` (async) |
| `mysql` | Drivers MySQL: `pymysql[rsa]` (sync) y `aiomysql` (async) |
| `migrate` | `sqlglot`: reescribe el SQL de las vistas al dialecto destino en `MigrationPlanner` |
| `analysis` | Grafos de relaciones entre tablas (Graphviz) |
| `analysis-matplotlib` | `MatplotlibRelationshipGraph` (matplotlib + networkx) |
| `doc-svg` | Render de SVG a otros formatos (CairoSVG) |
| `docs` | Construir el sitio de documentación (Zensical + MkDocs Material + mkdocstrings) |
| `dev` | Toolchain de desarrollo (pytest, ruff, mypy, build) |

!!! note
    La generación de documentación de BD (Word, Excel, HTML/Jinja2) **no requiere extra**: `openpyxl`, `python-docx` y `jinja2` forman parte de las dependencias base.

### Modo desarrollo (contribuidores)

```bash
git clone https://github.com/fmanza/util_bbdd.git
cd util_bbdd
python -m venv venv
# Windows:    si PowerShell bloquea el script (política "Restricted" por defecto), ejecuta antes:
#               Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
# Windows:    .\venv\Scripts\Activate.ps1
# Linux/Mac:  source venv/bin/activate
pip install -e ".[dev]"
```

### Construir la documentación (Zensical ↔ MkDocs)

La documentación usa **`mkdocs.yml` como única fuente de configuración**. El extra `docs`
instala dos generadores **compatibles de forma recíproca**, y ambos leen ese mismo
`mkdocs.yml`:

```bash
pip install -e ".[docs]"
```

| Generador | Servidor local | Build estático | Notas |
|---|---|---|---|
| **Zensical** (por defecto, lo usa el CI) | `zensical serve` | `zensical build` | Más rápido; lee `mkdocs.yml` nativamente |
| **MkDocs Material** (clásico) | `mkdocs serve` | `mkdocs build` | Compatibilidad recíproca con el mismo `mkdocs.yml` |

!!! note
    No existe un `zensical.toml` activo: Zensical lo priorizaría sobre `mkdocs.yml` si
    estuviera presente. La configuración se mantiene **solo en `mkdocs.yml`** para evitar
    duplicación. Ver [ZENICAL.md](https://github.com/fmanza/util_bbdd/blob/main/ZENICAL.md).

## 3. Drivers por Motor

Los drivers **no se incluyen** en la instalación básica; instálalos con el extra del motor o a mano:

| Motor | Driver sync | Driver async | Comando de instalación |
|---|---|---|---|
| PostgreSQL | `psycopg` 3 + `psycopg-pool` | `asyncpg` | extra `postgresql` (o `pip install "psycopg[binary]" psycopg-pool asyncpg`) |
| MariaDB (`db_type="mariadb"`) | `mariadb` (MariaDB Connector/Python) | `aiomysql` | extra `mariadb` (o `pip install mariadb aiomysql`) |
| MySQL (`db_type="mysql"`) | `pymysql` | `aiomysql` | extra `mysql` (o `pip install "pymysql[rsa]" aiomysql`) |
| SQLite | `sqlite3` (stdlib) | `aiosqlite` | extra `sqlite-async` (o `pip install aiosqlite`); sync incluido en Python |
| Oracle | `oracledb` | `oracledb` | extra `oracle` (o `pip install oracledb`) |
| SQL Server | `pymssql` (por defecto) o `pyodbc` | `aioodbc` | extra `sqlserver` (o `pip install pymssql`); con ODBC, extra `sqlserver-odbc` (o `pip install pyodbc aioodbc`) + ODBC Driver for SQL Server del SO |
| HSQLDB | `jaydebeapi` | N/A (sin async) | extra `hsqldb` (o `pip install JayDeBeApi`) + Java 8+ y el JAR de HSQLDB |

## 4. Verificación

Verificación sin servidor externo (SQLite en memoria):

```python
from util_bbdd import SyncDatabaseManager

with SyncDatabaseManager(db_type="sqlite", conn_params={"database": ":memory:"}) as mgr:
    mgr.execute_custom_many("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
    tablas = mgr.get_tables()
    print("Instalación correcta. Tablas:", [t.name for t in tablas])
    # → Instalación correcta. Tablas: ['test']
```

Verificación con un motor que requiere servidor (ejemplo PostgreSQL):

```bash
python -c "from util_bbdd import SyncDatabaseManager; m = SyncDatabaseManager('postgresql', {'host':'localhost','port':5432,'user':'postgres','password':'secret','database':'test'}); print('OK:', m.get_tables()); m.close()"
```

## 5. Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `Módulo psycopg (psycopg3) no disponible` | Driver PostgreSQL no instalado | Extra `postgresql` (o `pip install "psycopg[binary]" psycopg-pool`) |
| `No module named 'mariadb'` | Driver MariaDB no instalado | `pip install mariadb` (requiere MariaDB Connector/C en el sistema) |
| `No module named 'pymysql'` | Driver MySQL no instalado | `pip install "pymysql[rsa]"` |
| `'cryptography' package is required for sha256_password or caching_sha2_password` | MySQL 8 sin TLS necesita `cryptography` para autenticar | `pip install "pymysql[rsa]"` |
| `pyodbc.Error: ('IM002'...)` | ODBC driver de SQL Server no instalado en el SO | Instalar [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| `oracledb.DatabaseError: DPY-2014` | Oracle Instant Client no encontrado | Descargar Oracle Instant Client y configurar `oracle_client_path` en `conn_params` |
| `Timeout esperando conexión del pool` | Pool agotado | Aumentar `pool_size` en `conn_params` (`{"pool_size": 20, ...}`); `pool_timeout` existe en PostgreSQL, MySQL y SQL Server, y `max_overflow` en MySQL y SQL Server |
