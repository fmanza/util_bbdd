"""Modelos internos normalizados (IR) para metadatos de rutinas MariaDB."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MariaDBRoutineDetail:
    """Representa una rutina MariaDB decodificada desde information_schema.routines."""

    routine_name: str
    routine_type: str
    routine_comment: str
    definer: str
    security_type: str
    sql_data_access: str
    is_deterministic: str
    return_type: str
    sql_mode: str
    routine_definition: str

    def matches(self, *, routine_name: str, routine_type: str) -> bool:
        return (
            self.routine_name.upper() == str(routine_name or "").upper()
            and self.routine_type.upper() == str(routine_type or "").upper()
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "routine_name": self.routine_name,
            "routine_type": self.routine_type,
            "routine_comment": self.routine_comment,
            "definer": self.definer,
            "security_type": self.security_type,
            "sql_data_access": self.sql_data_access,
            "is_deterministic": self.is_deterministic,
            "return_type": self.return_type,
            "sql_mode": self.sql_mode,
            "routine_definition": self.routine_definition,
        }


@dataclass(frozen=True, slots=True)
class MariaDBRoutineParameterDetail:
    """Representa un parámetro de rutina MariaDB decodificado."""

    mode: str
    name: str
    routine_type: str
    routine_name: str
    data_type: str
    charset: str
    collation: str
    default_value: str
    ordinal_position: int | None

    def matches(self, *, routine_name: str, routine_type: str) -> bool:
        return (
            self.routine_name.upper() == str(routine_name or "").upper()
            and self.routine_type.upper() == str(routine_type or "").upper()
        )

    def to_public_row(self) -> tuple[str, str, str, str, int | None]:
        return (self.mode, self.name, self.data_type, self.default_value, self.ordinal_position)

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "name": self.name,
            "routine_type": self.routine_type,
            "routine_name": self.routine_name,
            "data_type": self.data_type,
            "charset": self.charset,
            "collation": self.collation,
            "default_value": self.default_value,
            "ordinal_position": self.ordinal_position,
        }


__all__: list[str] = ["MariaDBRoutineDetail", "MariaDBRoutineParameterDetail"]
