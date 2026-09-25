import logging, tempfile, shutil
from datetime import datetime
from pathlib import Path
import pandas as pd, sqlalchemy as sa
from util_bbdd.bulk import AuditManager, BulkCrud
from util_bbdd.dump.orchestrator import DumpOrchestrator
logging.disable(logging.CRITICAL)
T = Path(tempfile.mkdtemp())

def engine(name):
    e = sa.create_engine(f"sqlite:///{T/name}.db")
    with e.begin() as c: c.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, v INTEGER)")
    return e
def count(e):
    with e.connect() as c: return c.exec_driver_sql("SELECT COUNT(*) FROM t").scalar()

# R1: resumen del dump pierde operaciones terminadas en el mismo segundo que dump_inicio
p = T/"r1.csv"; desde = datetime.now()
AuditManager(p).registrar_operacion("t","SQLITE","INSERT",10,0.01)
s = DumpOrchestrator._build_audit_summary(p, desde)
print(f"R1 desde={desde.time()} csv_ts={pd.read_csv(p,sep=chr(9))['timestamp'][0]} -> summary={s}")

# R2: fallo de auditoría tras commit (fuera de sesión): excepción al llamador pero filas persistidas
e = engine("r2"); p = T/"r2.csv"; crud = BulkCrud(e, audit_csv_path=p)
p.mkdir()  # el destino ya no es escribible como fichero
try:
    crud.bulk_insert_from_df(pd.DataFrame({"id":[1,2,3],"v":[1,2,3]}), "t", generar_sql=False); print("R2 sin error")
except Exception as ex:
    print(f"R2 excepción={type(ex).__name__} ; filas en BD={count(e)} (reintento => IntegrityError/duplicados)")

# R3: streaming atómico: chunk 2 falla -> rollback total, pero el CSV conserva el chunk 1
e = engine("r3"); p = T/"r3.csv"; crud = BulkCrud(e, audit_csv_path=p)
chunks = [pd.DataFrame({"id":range(0,100),"v":0}), pd.DataFrame({"id":[5],"v":0})]  # duplicado de PK
try: crud.bulk_insert_from_chunks(iter(chunks), "t")
except Exception as ex: pass
a = pd.read_csv(p, sep="\t") if p.exists() else pd.DataFrame({"total_filas": []})
print(f"R3 filas en BD={count(e)} ; CSV dice INSERT total_filas={int(a['total_filas'].sum())} en {len(a)} registro(s)")

# R4: CSV existente vacío (touch / truncado por rotación) -> nunca se escribe cabecera
p = T/"r4.csv"; p.touch(); m = AuditManager(p, cache_enabled=False)
m.registrar_operacion("t","SQLITE","INSERT",10,0.01)
df = m.leer_auditoria(); print(f"R4 columnas leídas={list(df.columns)}")
try: m.obtener_estadisticas()
except Exception as ex: print(f"R4 obtener_estadisticas -> {type(ex).__name__}: {str(ex)[:80]}")

# R5: DELETE registra filas enviadas, no afectadas
e = engine("r5"); p = T/"r5.csv"; crud = BulkCrud(e, audit_csv_path=p)
crud.bulk_insert_from_df(pd.DataFrame({"id":[1,2],"v":[0,0]}), "t", generar_sql=False)
crud.bulk_delete_from_df(pd.DataFrame({"id":list(range(1,1001))}), "t", generar_sql=False)
a = pd.read_csv(p, sep="\t"); print(f"R5 DELETE en CSV total_filas={a.iloc[-1]['total_filas']} ; filas realmente borradas=2")

# R6: caché obsoleta entre instancias sobre el mismo CSV
p = T/"r6.csv"; A = AuditManager(p); B = AuditManager(p)
A.registrar_operacion("t","SQLITE","INSERT",1,0.0); n1 = len(A.leer_auditoria())
B.registrar_operacion("t","SQLITE","INSERT",1,0.0); n2 = len(A.leer_auditoria())
print(f"R6 A ve {n1} -> tras escribir B, A ve {n2} (real 2)")

# R7: setter columnas_auditoria desalinea cabecera y fila
p = T/"r7.csv"; m = AuditManager(p, cache_enabled=False); m.columnas_auditoria = ["timestamp","tabla"]
m.registrar_operacion("t","SQLITE","INSERT",1,0.0)
try: print(f"R7 lectura -> columnas {list(m.leer_auditoria().columns)}")
except Exception as ex: print(f"R7 lectura -> {type(ex).__name__}: {str(ex)[:90]}")

# R8: validar_ruta lanza ValueError, no AuditError (el except (AuditError, OSError) de crud no aplica; aquí en __init__)
import inspect; from util_bbdd.bulk._audit import repository as r
print("R8 validar_ruta lanza ValueError:", "raise ValueError" in inspect.getsource(r.AuditCsvRepository.validar_ruta))
shutil.rmtree(T, ignore_errors=True)
