"""Contadores de auditoría de una carga bulk como valor sumable.

``BulkCrud``, ``ParallelLoadResult`` y ``PartitionResult`` exponen los mismos cuatro contadores; ``ParallelBulkLoader`` y
``dump`` los copian y los suman con este valor en lugar de repetir los nombres campo a campo.

Movido desde ``util_bbdd.bulk._audit.counters`` (sesión 2026-10-02c) sin cambios; aquel módulo lo re-exporta.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol


class SupportsAuditCounters(Protocol):
    """Cualquier objeto con los cuatro contadores de auditoría (``BulkCrud``, ``ParallelLoadResult``)."""

    @property
    def audit_failures(self) -> int: ...

    @property
    def audited_rows(self) -> int: ...

    @property
    def unaudited_committed_rows(self) -> int: ...

    @property
    def audit_uncommitted_records(self) -> int: ...


@dataclass(frozen=True)
class AuditCounters:
    """Contadores de auditoría; ``BulkCrud`` y ``ParallelLoadResult`` exponen los mismos nombres."""

    audit_failures: int = 0
    audited_rows: int = 0
    unaudited_committed_rows: int = 0
    audit_uncommitted_records: int = 0

    @classmethod
    def of(cls, source: SupportsAuditCounters) -> AuditCounters:
        """Copia los contadores de ``source``."""
        return cls(
            audit_failures=source.audit_failures,
            audited_rows=source.audited_rows,
            unaudited_committed_rows=source.unaudited_committed_rows,
            audit_uncommitted_records=source.audit_uncommitted_records,
        )

    def __add__(self, other: AuditCounters) -> AuditCounters:
        return AuditCounters(
            audit_failures=self.audit_failures + other.audit_failures,
            audited_rows=self.audited_rows + other.audited_rows,
            unaudited_committed_rows=self.unaudited_committed_rows + other.unaudited_committed_rows,
            audit_uncommitted_records=self.audit_uncommitted_records + other.audit_uncommitted_records,
        )

    def as_dict(self) -> dict[str, int]:
        """Los cuatro contadores por nombre, para pasarlos como ``**kwargs`` a los resultados que los tienen planos."""
        return asdict(self)


__all__: list[str] = ["AuditCounters", "SupportsAuditCounters"]
