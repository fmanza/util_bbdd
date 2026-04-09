"""Modelos internos normalizados (IR) para metadatos de Oracle."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OracleRoutineDetail:
    """Representa una rutina Oracle decodificada desde all_procedures."""

    routine_name: str
    routine_type: str  # PROCEDURE, FUNCTION, PACKAGE, PACKAGE BODY
    routine_owner: str
    object_id: int | None = None

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
            "object_id": self.object_id,
        }


@dataclass(frozen=True, slots=True)
class OracleParameterDetail:
    """Representa un parámetro de función/procedimiento Oracle desde all_arguments."""

    param_name: str
    routine_name: str
    routine_type: str  # PROCEDURE, FUNCTION, etc
    routine_owner: str
    in_out: str  # IN, OUT, INOUT, RETURN
    data_type: str
    data_length: int | None = None
    data_precision: int | None = None
    data_scale: int | None = None
    ordinal_position: int | None = None
    object_id: int | None = None
    argument_id: int | None = None

    def matches(self, *, routine_name: str, routine_type: str) -> bool:
        """Compara nombres y tipo de rutina del parámetro."""
        return (
            self.routine_name.upper() == str(routine_name or "").upper()
            and self.routine_type.upper() == str(routine_type or "").upper()
        )

    def to_public_row(self) -> tuple[str, str, str, int | None]:
        """Convierte a fila pública para API (mode, name, data_type, ordinal)."""
        return (self.in_out, self.param_name, self.data_type, self.ordinal_position)

    def to_dict(self) -> dict[str, object]:
        """Convierte a diccionario para serialización."""
        return {
            "param_name": self.param_name,
            "routine_name": self.routine_name,
            "routine_type": self.routine_type,
            "routine_owner": self.routine_owner,
            "in_out": self.in_out,
            "data_type": self.data_type,
            "data_length": self.data_length,
            "data_precision": self.data_precision,
            "data_scale": self.data_scale,
            "ordinal_position": self.ordinal_position,
            "object_id": self.object_id,
            "argument_id": self.argument_id,
        }


__all__: list[str] = [
    "OracleRoutineDetail",
    "OracleParameterDetail",
]
