# URLs de los servidores del banco (docker-compose.bench.yml) para scripts/bench_bulk.py y los tests de integración.
#
#   export UTIL_BBDD_BENCH_PASSWORD=...          # la misma con la que se levantaron los contenedores
#   source scripts/bench_env.example.sh
#
# Define UTIL_BBDD_BENCH_<MOTOR>_URL y UTIL_BBDD_TEST_<MOTOR>_URL apuntando solo a los contenedores del banco (127.0.0.1 y
# sus puertos, nunca los estándar). Respeta los puertos cambiados con UTIL_BBDD_BENCH_<MOTOR>_PORT. La contraseña no se
# guarda en este fichero; si lleva símbolos, codifícala para URL.

if [ -z "${UTIL_BBDD_BENCH_PASSWORD:-}" ]; then
    echo "Define UTIL_BBDD_BENCH_PASSWORD (la de docker-compose.bench.yml) antes de cargar este fichero" >&2
    return 1 2>/dev/null || exit 1
fi

_bench_pw="$UTIL_BBDD_BENCH_PASSWORD"
_bench_host="127.0.0.1"
for _bench_prefix in BENCH TEST; do
    export "UTIL_BBDD_${_bench_prefix}_POSTGRESQL_URL=postgresql+psycopg://bench:${_bench_pw}@${_bench_host}:${UTIL_BBDD_BENCH_POSTGRES_PORT:-55432}/bench"
    export "UTIL_BBDD_${_bench_prefix}_MYSQL_URL=mysql+pymysql://bench:${_bench_pw}@${_bench_host}:${UTIL_BBDD_BENCH_MYSQL_PORT:-53306}/bench"
    export "UTIL_BBDD_${_bench_prefix}_MARIADB_URL=mariadb+pymysql://bench:${_bench_pw}@${_bench_host}:${UTIL_BBDD_BENCH_MARIADB_PORT:-53307}/bench"
    # SQL Server con pyodbc: mssql+pyodbc://sa:<clave>@127.0.0.1:51433/bench?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
    export "UTIL_BBDD_${_bench_prefix}_MSSQL_URL=mssql+pymssql://sa:${_bench_pw}@${_bench_host}:${UTIL_BBDD_BENCH_MSSQL_PORT:-51433}/bench"
    export "UTIL_BBDD_${_bench_prefix}_ORACLE_URL=oracle+oracledb://bench:${_bench_pw}@${_bench_host}:${UTIL_BBDD_BENCH_ORACLE_PORT:-51521}/?service_name=FREEPDB1"
done
unset _bench_pw _bench_host _bench_prefix
