"""Ejemplo: normalizar registros de un DataFrame para SQL e inferir tipos SQLAlchemy de sus columnas.

No usa base de datos: muestra la transformación que hace BulkCrud antes de enviar las filas al driver.
"""

import numpy as np
import pandas as pd

from util_bbdd.bulk import normalize_records_for_sql
from util_bbdd.bulk.normalize import pandas_dtype_to_sqlalchemy

df = pd.DataFrame(
    {
        "id": np.array([1, 2]),
        "alta": pd.to_datetime(["2026-01-01", None]),
        "nombre": [" Ana ", "Luis"],
        "saldo": [10.5, float("nan")],
    }
)

# 1. Registros listos para el driver: tipos de numpy/pandas a nativos de Python, NaT/NaN a None, texto recortado
for record in normalize_records_for_sql(df.to_dict("records")):
    print(record)

# 2. Tipo SQLAlchemy inferido de cada columna (lo que usa BulkCrud al crear una tabla desde el DataFrame)
#    Devuelve la clase (Integer) o, si lleva longitud, una instancia (String(length=6)); aquí se muestran instanciadas
for column in df.columns:
    sql_type = pandas_dtype_to_sqlalchemy(df[column])
    print(f"{column}: {(sql_type() if isinstance(sql_type, type) else sql_type)!r}")
