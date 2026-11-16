# Cargar desde origen SQL (no CSV)
import pandas as pd

from sqlalchemy import text


def make_reader_from_sql(source_engine, lo, hi):
    """Lector que extrae datos de una partición desde SQL."""

    def _reader():
        sql = "SELECT * FROM source_table WHERE id >= :lo AND id < :hi"
        with source_engine.connect() as conn:
            for chunk in pd.read_sql(text(sql), conn, params={"lo": lo, "hi": hi}, chunksize=5_000):
                yield chunk

    return _reader
