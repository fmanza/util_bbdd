"""Modelos internos normalizados (IR) para metadatos de PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PgRoutineDetail:
    """Representa una rutina PostgreSQL decodificada desde pg_proc y pg_namespace."""

    routine_name: str
    routine_type: str
    routine_owner: str
    routine_definition: str
    return_type: str
    is_aggregate: bool = False
    is_window: bool = False
    security_definer: bool = False

    def matches(self, *, routine_name: str, routine_type: str) -> bool:
        """Compara nombres y tipos de rutina."""
        return (
            self.routine_name.upper() == str(routine_name or "").upper()
            and self.routine_type.upper() == str(routine_type or "").upper()
        )

    def to_dict(self) -> dict[str, object]:
        """Convierte a diccionario para serialización."""
        return {
            "routine_name": self.routine_name,
            "routine_type": self.routine_type,
            "routine_owner": self.routine_owner,
            "routine_definition": self.routine_definition,
            "return_type": self.return_type,
            "is_aggregate": self.is_aggregate,
            "is_window": self.is_window,
            "security_definer": self.security_definer,
        }


@dataclass(frozen=True, slots=True)
class PgParameterDetail:
    """Representa un parámetro de función/procedimiento PostgreSQL."""

    mode: str
    name: str
    routine_name: str
    routine_type: str
    data_type: str
    ordinal_position: int | None = None
    default_value: str | None = None

    def matches(self, *, routine_name: str, routine_type: str) -> bool:
        """Compara nombres y tipo de rutina del parámetro."""
        return (
            self.routine_name.upper() == str(routine_name or "").upper()
            and self.routine_type.upper() == str(routine_type or "").upper()
        )

    def to_public_row(self) -> tuple[str, str, str, str | None, int | None]:
        """Convierte a fila pública para API (mode, name, data_type, default, ordinal)."""
        return (self.mode, self.name, self.data_type, self.default_value, self.ordinal_position)

    def to_dict(self) -> dict[str, object]:
        """Convierte a diccionario para serialización."""
        return {
            "mode": self.mode,
            "name": self.name,
            "routine_name": self.routine_name,
            "routine_type": self.routine_type,
            "data_type": self.data_type,
            "ordinal_position": self.ordinal_position,
            "default_value": self.default_value,
        }
