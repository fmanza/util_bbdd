"""Ejemplo: verificar las condiciones del motor antes de una carga masiva con EngineReadinessAdvisor.

Usa un fichero SQLite en el directorio actual; no requiere servidor externo.
"""

from pathlib import Path

from util_bbdd import SyncDatabaseManager
from util_bbdd.connection import EngineReadinessAdvisor

advisor = EngineReadinessAdvisor()

# 1. Checks estáticos: solo leen conn_params, no conectan
findings = advisor.check("sqlite", {"database": "carga.db", "timeout": 2.0})
for f in findings:
    print(f"{f.level:8} {f.param} = {f.current}")
    if f.recommendation:
        print(f"         → {f.recommendation}")

# 2. Informe completo con los checks dinámicos (PRAGMA del fichero real)
db_path = Path("carga.db")
with SyncDatabaseManager(db_type="sqlite", conn_params={"database": str(db_path)}) as manager:
    report = manager.get_engine_readiness()
    print(f"motor={report.db_type} soportado={report.supported} dinámico={report.dynamic} error={report.error}")
    for f in report.findings:
        print(f"{f.level:8} {f.param} = {f.current}")

# 3. Un motor sin checks (HSQLDB) devuelve un informe vacío, no un error
sin_checks = advisor.assess("hsqldb", {})
print(f"hsqldb soportado={sin_checks.supported} hallazgos={len(sin_checks.findings)}")

db_path.unlink(missing_ok=True)
