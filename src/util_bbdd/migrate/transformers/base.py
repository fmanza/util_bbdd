"""Protocol base para transformadores de esquemas."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ir.models import CanonicalRoutine, CanonicalTable, CanonicalView


@runtime_checkable
class SchemaTransformer(Protocol):
    """Contrato para transformadores IR origen → IR destino."""

    def transform(self, tables: list[CanonicalTable]) -> list[CanonicalTable]:
        """Transforma una lista de tablas IR al esquema destino.

        Args:
            tables: Tablas extraídas del motor origen.

        Returns:
            Tablas transformadas con tipos destino y warnings poblados.
        """
        ...

    def transform_views(self, views: list[CanonicalView]) -> list[CanonicalView]:
        """Transforma una lista de vistas IR al esquema destino.

        MIG-06 (AUDIT_CODE 2026-09-22): esta iteración (``BaseTransformer.
        transform_views``) es común a los 12 pares origen→destino y nunca se
        sobrescribe; lo que varía por par es el hook privado
        ``_transform_view``. Por defecto (pass-through v1) solo verifica
        identificadores, sin tocar el SQL. Solo los 3 pares con Oracle como
        origen (``oracle_to_mariadb``, ``oracle_to_postgresql``,
        ``oracle_to_sqlserver``) invocan ``rewrite_oracle_view`` desde ese
        hook para aplicar reescritura best-effort del SQL: sustituyen
        SYSDATE, NVL, FROM DUAL, hints y prefijos de schema. Constructs
        complejos (ROWNUM, CONNECT BY, outer-join (+), DECODE) generan
        MigrationWarning en esos 3 pares. Otros pares pueden sobrescribir
        ``_transform_view`` por motivos ajenos a la reescritura SQL (p.ej.
        advertencias de revisión manual) sin invocar ese rewriter.

        Args:
            views: Vistas extraídas del motor origen.

        Returns:
            Vistas transformadas (SQL reescrito solo si el origen es Oracle)
            con warnings poblados.
        """
        ...

    def transform_routines(self, routines: list[CanonicalRoutine]) -> list[CanonicalRoutine]:
        """Transforma una lista de rutinas IR al esquema destino.

        Pass-through v1: aplica verificación de identificadores y emite
        MigrationWarning invitando a revisión manual del body. No reescribe
        el cuerpo DDL.

        Args:
            routines: Rutinas extraídas del motor origen.

        Returns:
            Rutinas con warnings poblados.
        """
        ...


__all__: list[str] = ["SchemaTransformer"]
