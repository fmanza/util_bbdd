"""Particionamiento de datos por rango de PK para ParallelBulkLoader.

``RangePartitioner`` genera rangos o sub-DataFrames disjuntos a partir de una
columna entera o datetime64, listos para usarse como ``PartitionReader`` en
``ParallelBulkLoader``.
"""

from __future__ import annotations

import math

import pandas as pd


class RangePartitioner:
    """Genera particiones disjuntas por rango de columna PK para carga paralela.

    Solo soporta columnas de tipo entero (``int``, ``np.integer``) o
    ``datetime64`` en ``partition_dataframe``. Para otros tipos, construye
    los rangos externamente y usa ``partition_ranges`` para subdividirlos.

    Ejemplo con DataFrame en memoria::

        partitions = RangePartitioner.partition_dataframe(df, pk_col="id", n_partitions=4)
        readers = [lambda df=p: iter([df]) for p in partitions]
        result = ParallelBulkLoader(engine, max_workers=4).load("orders", readers)

    Ejemplo con rangos para lectores SQL (sin materializar todo el DataFrame)::

        ranges = RangePartitioner.partition_ranges(1, 13_000_000, n_partitions=8)
        readers = [
            lambda lo=lo, hi=hi: pd.read_sql(
                "SELECT * FROM orders WHERE id BETWEEN :lo AND :hi",
                engine,
                params={"lo": lo, "hi": hi},
                chunksize=5000,
            )
            for lo, hi in ranges
        ]
        result = ParallelBulkLoader(engine, max_workers=8).load("orders", readers)
    """

    @staticmethod
    def partition_dataframe(
        df: pd.DataFrame,
        pk_col: str,
        n_partitions: int,
    ) -> list[pd.DataFrame]:
        """Divide ``df`` en ``n_partitions`` slices ordenados por ``pk_col``.

        Devuelve slices del DataFrame ordenado (vistas cuando es posible),
        minimizando el uso de memoria. Si ``len(df) < n_partitions``, devuelve
        tantas particiones como filas.

        Args:
            df: DataFrame a particionar.
            pk_col: Columna entera o datetime64 por la que ordenar y dividir.
            n_partitions: Número de particiones deseado. Debe ser ≥ 1.

        Returns:
            Lista de DataFrames disjuntos. El último puede ser más pequeño si
            ``len(df)`` no es divisible exactamente entre ``n_partitions``.

        Raises:
            ValueError: Si ``pk_col`` no existe en ``df`` o ``n_partitions < 1``.
            TypeError: Si ``pk_col`` no es de tipo entero o datetime64.
        """
        if n_partitions < 1:
            raise ValueError(f"n_partitions debe ser ≥ 1, recibido: {n_partitions}")
        if pk_col not in df.columns:
            raise ValueError(f"Columna '{pk_col}' no existe en el DataFrame.")

        RangePartitioner._validate_column_type(df[pk_col], pk_col)

        sorted_df = df.sort_values(pk_col, ignore_index=True)
        total = len(sorted_df)
        if total == 0:
            return [sorted_df]

        actual_parts = min(n_partitions, total)
        size = math.ceil(total / actual_parts)
        return [sorted_df.iloc[start : start + size] for start in range(0, total, size)]

    @staticmethod
    def partition_ranges(
        min_val: int,
        max_val: int,
        n_partitions: int,
    ) -> list[tuple[int, int]]:
        """Genera ``n_partitions`` rangos ``[lo, hi]`` (inclusivos) que cubren
        ``[min_val, max_val]``.

        Útil para construir lectores SQL con ``WHERE pk BETWEEN :lo AND :hi``.
        Los rangos no se solapan: el ``hi`` de cada rango es el ``lo - 1`` del
        siguiente. El último rango extiende siempre hasta ``max_val``.

        Args:
            min_val: Valor mínimo del rango (inclusivo).
            max_val: Valor máximo del rango (inclusivo). Debe ser ≥ ``min_val``.
            n_partitions: Número de rangos. Debe ser ≥ 1.

        Returns:
            Lista de tuplas ``(lo, hi)`` (ambos extremos inclusivos).

        Raises:
            ValueError: Si ``min_val > max_val`` o ``n_partitions < 1``.

        Ejemplo::

            >>> RangePartitioner.partition_ranges(1, 10, 3)
            [(1, 4), (5, 8), (9, 10)]
        """
        if n_partitions < 1:
            raise ValueError(f"n_partitions debe ser ≥ 1, recibido: {n_partitions}")
        if min_val > max_val:
            raise ValueError(f"min_val ({min_val}) > max_val ({max_val})")

        total = max_val - min_val + 1
        step = math.ceil(total / n_partitions)
        ranges: list[tuple[int, int]] = []
        lo = min_val
        while lo <= max_val:
            hi = min(lo + step - 1, max_val)
            ranges.append((lo, hi))
            lo = hi + 1
        return ranges

    @staticmethod
    def _validate_column_type(series: pd.Series, pk_col: str) -> None:
        """Lanza ``TypeError`` si ``series`` no es de tipo entero o datetime64."""
        dtype = series.dtype
        is_int = pd.api.types.is_integer_dtype(dtype)
        is_dt = pd.api.types.is_datetime64_any_dtype(dtype)
        if not (is_int or is_dt):
            raise TypeError(
                f"RangePartitioner solo admite columnas enteras o datetime64. "
                f"Columna '{pk_col}' tiene dtype '{dtype}'. "
                f"Para PKs de tipo string o UUID, construye los rangos externamente "
                f"y usa partition_ranges() con los valores enteros de los límites."
            )


class HashPartitioner:
    """Particiones por hash de columna para tipos no admitidos por ``RangePartitioner``.

    A diferencia de :class:`RangePartitioner`, acepta cualquier tipo hashable
    (``str``, ``UUID``, ``bytes``, etc.) usando ``pandas.util.hash_pandas_object``
    para asignar cada fila al bucket ``hash % n_partitions``.

    La distribución es estadísticamente uniforme para columnas con alta cardinalidad,
    pero no garantiza particiones del mismo tamaño. Para PKs enteras o datetime se
    recomienda :class:`RangePartitioner` (distribución garantizada por posición).

    Ejemplo::

        partitions = HashPartitioner.partition_dataframe(df, pk_col="uuid_col", n_partitions=4)
        readers = [lambda df=p: iter([df]) for p in partitions]
        result = ParallelBulkLoader(engine, max_workers=4).load("orders", readers)
    """

    @staticmethod
    def partition_dataframe(
        df: pd.DataFrame,
        pk_col: str,
        n_partitions: int,
    ) -> list[pd.DataFrame]:
        """Divide ``df`` en hasta ``n_partitions`` particiones usando hash de ``pk_col``.

        Cada fila se asigna al bucket ``hash(pk_col) % n_partitions``. Los buckets vacíos
        no se incluyen en el resultado, por lo que la lista puede tener menos de
        ``n_partitions`` elementos si la columna tiene baja cardinalidad.

        Args:
            df: DataFrame a particionar.
            pk_col: Columna por la que particionar. Acepta cualquier tipo hashable.
            n_partitions: Número máximo de particiones. Debe ser ≥ 1.

        Returns:
            Lista de DataFrames disjuntos. Puede tener menos de ``n_partitions``
            elementos si algún bucket hash queda vacío.

        Raises:
            ValueError: Si ``pk_col`` no existe en ``df`` o ``n_partitions < 1``.
        """
        if n_partitions < 1:
            raise ValueError(f"n_partitions debe ser ≥ 1, recibido: {n_partitions}")
        if pk_col not in df.columns:
            raise ValueError(f"Columna '{pk_col}' no existe en el DataFrame.")
        if df.empty:
            return [df.iloc[:0].copy()]

        hash_vals = pd.util.hash_pandas_object(df[pk_col], index=False)
        assignments = hash_vals % n_partitions
        return [
            df[assignments == bucket].copy()
            for bucket in range(n_partitions)
            if (assignments == bucket).any()
        ]


__all__: list[str] = ["HashPartitioner", "RangePartitioner"]
