# Factory de lectores de partición
import pandas as pd


def make_reader(lo: int, hi: int):
    """Crea un lector que extrae una partición del CSV en rango [lo, hi)."""

    def _reader():
        # Leer datos del rango [lo, hi)
        df = pd.read_csv("source.csv")
        df_part = df[(df["id"] >= lo) & (df["id"] < hi)]
        # Devolver en chunks
        for i in range(0, len(df_part), 5_000):
            yield df_part.iloc[i : i + 5_000]

    return _reader
