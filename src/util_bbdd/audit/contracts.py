"""Contratos del módulo de auditoría: dónde se escriben los eventos y de dónde se leen.

Escritura (:class:`AuditSink`) y lectura (:class:`AuditEventSource`) van separadas (ISP): un destino de solo añadir
(fichero JSON Lines, un sistema externo del usuario) no tiene por qué saber leer.

El CSV de auditoría de ``bulk`` (:mod:`util_bbdd.audit.legacy_csv`) no implementa estos contratos: su formato está
congelado y su lectura devuelve un ``DataFrame``, no eventos.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from .events import AuditEvent


@runtime_checkable
class AuditSink(Protocol):
    """Destino de eventos de auditoría.

    Contrato que deben cumplir todas las implementaciones (lo comprueba ``tests/unit/audit/test_sinks_contract.py``):

    - ``write`` es atómico por llamada: o se escriben todos los eventos de ``events`` o ninguno queda a medias de forma
      visible para otro hilo (los de una llamada no se intercalan con los de otra).
    - ``write`` es seguro con varios hilos sobre la misma instancia.
    - ``write`` con una secuencia vacía no hace nada.
    - ``close`` es idempotente; ``write`` después de ``close`` lanza ``ValueError``.
    - Un fallo de escritura se propaga (``OSError``…): quien llama decide si la operación auditada falla (la política
      ``audit_strict`` de ``bulk``).
    """

    def write(self, events: Sequence[AuditEvent], /) -> None:
        """Añade ``events`` al destino (atómico por llamada; ver el contrato de la clase).

        Args:
            events: Eventos a escribir, en orden; una secuencia vacía no hace nada.

        Raises:
            ValueError: Si el destino ya está cerrado.
            OSError: Si falla la escritura (se propaga; quien llama decide si la operación auditada falla).
        """
        ...

    def close(self) -> None:
        """Libera los recursos del destino."""
        ...


@runtime_checkable
class AuditEventSource(Protocol):
    """Origen de eventos ya escritos, en orden de escritura."""

    def events(self) -> Sequence[AuditEvent]:
        """Copia de los eventos escritos hasta ahora."""
        ...


__all__: list[str] = ["AuditEventSource", "AuditSink"]
