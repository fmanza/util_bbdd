"""Locks por ruta compartidos en el proceso para los ficheros de auditoría (CSV de auditoría, rechazos, JSON Lines).

Varias instancias que escriben en el **mismo** fichero (una ``BulkCrud`` por hilo en el volcado paralelo, una
``AuditManager`` por partición de ``ParallelBulkLoader``) serializan sus escrituras con el mismo lock, para no intercalar
filas ni duplicar cabeceras. El alcance es intra-proceso (hilos): no coordina procesos distintos (H-05, descartado).

Debe existir **un solo** registro en el proceso: ``util_bbdd.bulk._audit.repository._get_file_lock`` es este mismo
:func:`path_lock` re-exportado, nunca una copia (dos registros darían dos locks para el mismo fichero).
"""

from __future__ import annotations

import os
import threading

from pathlib import Path

# Única excepción documentada a "sin estado global mutable": el registro tiene que ser común a todas las instancias.
_FILE_LOCKS: dict[str, threading.Lock] = {}
_FILE_LOCKS_GUARD = threading.Lock()


def path_lock(path: Path) -> threading.Lock:
    """Devuelve el lock compartido para ``path`` (creándolo si no existe).

    La clave se normaliza para que rutas relativa y absoluta (y, en Windows, con distinta capitalización) al mismo
    fichero compartan el mismo lock. Es una normalización de texto, sin consultar el disco: ``Path.resolve()`` en
    Windows devolvía ``\\\\?\\C:\\...`` mientras el fichero se estaba renombrando (al apartar un CSV con cabecera ajena) y
    ``C:\\...`` el resto del tiempo, así que dos hilos obtenían locks distintos y uno pisaba la cabecera y las filas del
    otro.

    Examples:
        >>> path_lock(Path("auditoria.csv")) is path_lock(Path("./auditoria.csv"))
        True
    """
    key = os.path.normcase(os.path.abspath(path))
    with _FILE_LOCKS_GUARD:
        lock = _FILE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _FILE_LOCKS[key] = lock
        return lock


__all__: list[str] = ["path_lock"]
