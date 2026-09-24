# URLs de los servidores del banco (docker-compose.bench.yml) para scripts/bench_bulk.py y los tests de integración.
#
#   $env:UTIL_BBDD_BENCH_PASSWORD = "..."        # la misma con la que se levantaron los contenedores
#   . scripts\bench_env.example.ps1
#
# Define UTIL_BBDD_BENCH_<MOTOR>_URL y UTIL_BBDD_TEST_<MOTOR>_URL apuntando solo a los contenedores del banco (127.0.0.1 y
# sus puertos, nunca los estándar). Respeta los puertos cambiados con UTIL_BBDD_BENCH_<MOTOR>_PORT. La contraseña no se
# guarda en este fichero; si lleva símbolos, codifícala para URL.

if (-not $env:UTIL_BBDD_BENCH_PASSWORD) {
    throw 'Define $env:UTIL_BBDD_BENCH_PASSWORD (la de docker-compose.bench.yml) antes de cargar este fichero'
}

function Get-BenchPort([string]$Name, [int]$Default) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ($value) { return $value }
    return $Default
}

$benchPw = $env:UTIL_BBDD_BENCH_PASSWORD
$benchHost = '127.0.0.1'
$benchUrls = @{
    POSTGRESQL = "postgresql+psycopg://bench:${benchPw}@${benchHost}:$(Get-BenchPort 'UTIL_BBDD_BENCH_POSTGRES_PORT' 55432)/bench"
    MYSQL      = "mysql+pymysql://bench:${benchPw}@${benchHost}:$(Get-BenchPort 'UTIL_BBDD_BENCH_MYSQL_PORT' 53306)/bench"
    MARIADB    = "mariadb+pymysql://bench:${benchPw}@${benchHost}:$(Get-BenchPort 'UTIL_BBDD_BENCH_MARIADB_PORT' 53307)/bench"
    # SQL Server con pyodbc: mssql+pyodbc://sa:<clave>@127.0.0.1:51433/bench?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
    MSSQL      = "mssql+pymssql://sa:${benchPw}@${benchHost}:$(Get-BenchPort 'UTIL_BBDD_BENCH_MSSQL_PORT' 51433)/bench"
    ORACLE     = "oracle+oracledb://bench:${benchPw}@${benchHost}:$(Get-BenchPort 'UTIL_BBDD_BENCH_ORACLE_PORT' 51521)/?service_name=FREEPDB1"
}
foreach ($prefix in 'BENCH', 'TEST') {
    foreach ($engine in $benchUrls.Keys) {
        Set-Item -Path "env:UTIL_BBDD_${prefix}_${engine}_URL" -Value $benchUrls[$engine]
    }
}
Remove-Variable benchPw, benchHost, benchUrls
