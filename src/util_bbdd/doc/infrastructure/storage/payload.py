"""Payloads tipados para el runtime de inventario de almacenamiento."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

StorageStatus = Literal["ok", "not_supported", "missing_params", "error"]
StorageCell = object


@dataclass(slots=True, frozen=True)
class StorageRowPayload:
    """Fila tabular del inventario de almacenamiento."""

    values: tuple[StorageCell, ...]

    @classmethod
    def from_sequence(cls, values: Sequence[object]) -> StorageRowPayload:
        """Construye la fila a partir de una secuencia posicional."""
        return cls(values=tuple(values))

    def to_list(self) -> list[StorageCell]:
        """Devuelve la fila en formato lista."""
        return list(self.values)


@dataclass(slots=True, frozen=True)
class StorageSectionPayload:
    """Sección tipada del informe de almacenamiento."""

    query: str
    title: str
    status: StorageStatus
    message: str
    sql: str
    headers: tuple[str, ...]
    rows: tuple[StorageRowPayload, ...]
    numeric_columns: tuple[int, ...]

    @classmethod
    def from_mapping(cls, raw_section: Mapping[str, object]) -> StorageSectionPayload:
        """Normaliza un diccionario raw a payload tipado."""
        raw_rows: object = raw_section.get("rows", [])
        section_rows: list[StorageRowPayload] = []
        if isinstance(raw_rows, list):
            for row in raw_rows:
                if isinstance(row, (list, tuple)):
                    section_rows.append(StorageRowPayload.from_sequence(row))
                else:
                    section_rows.append(StorageRowPayload.from_sequence([row]))

        raw_headers: object = raw_section.get("headers", [])
        headers: tuple[str, ...] = tuple(str(header) for header in raw_headers) if isinstance(raw_headers, list) else ()

        raw_numeric_columns: object = raw_section.get("numeric_columns", [])
        numeric_columns: tuple[int, ...]
        if isinstance(raw_numeric_columns, list):
            numeric_columns = tuple(int(index) for index in raw_numeric_columns)
        else:
            numeric_columns = ()

        raw_status: str = str(raw_section.get("status", "error"))
        status: StorageStatus = cast(StorageStatus, raw_status)

        return cls(
            query=str(raw_section.get("query", "")),
            title=str(raw_section.get("title", "")),
            status=status,
            message=str(raw_section.get("message", "")),
            sql=str(raw_section.get("sql", "")),
            headers=headers,
            rows=tuple(section_rows),
            numeric_columns=numeric_columns,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa la sección al formato legacy consumido por renderers."""
        return {
            "query": self.query,
            "title": self.title,
            "status": self.status,
            "message": self.message,
            "sql": self.sql,
            "headers": list(self.headers),
            "rows": [row.to_list() for row in self.rows],
            "numeric_columns": list(self.numeric_columns),
        }


@dataclass(slots=True, frozen=True)
class StorageInventoryReportPayload:
    """Payload tipado del informe de inventario de almacenamiento."""

    db_type: str
    database: str
    tablespace: str
    sections: tuple[StorageSectionPayload, ...]

    @property
    def total_rows(self) -> int:
        """Total de filas exitosas del informe."""
        return sum(len(section.rows) for section in self.sections if section.status == "ok")

    def to_dict(self) -> dict[str, Any]:
        """Serializa el informe al formato legacy consumido por renderers."""
        return {
            "db_type": self.db_type,
            "database": self.database,
            "tablespace": self.tablespace,
            "total_rows": self.total_rows,
            "sections": [section.to_dict() for section in self.sections],
        }
