"""Helpers internos para decode y normalizacion de rutinas MariaDB."""

from __future__ import annotations

from ...results import Rows
from ._routine_models import MariaDBRoutineDetail, MariaDBRoutineParameterDetail
from .common import decode_mariadb_hex_text


def decode_mariadb_routine_detail_entries(rows: Rows) -> list[MariaDBRoutineDetail]:
    """Decodifica filas detalladas de information_schema.routines a IR tipado."""
    decoded_rows: list[MariaDBRoutineDetail] = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 10:
            continue
        decoded_rows.append(
            MariaDBRoutineDetail(
                routine_name=decode_mariadb_hex_text(row[0]).strip(),
                routine_type=str(row[1] or "").strip().upper(),
                routine_comment=decode_mariadb_hex_text(row[2]).strip(),
                definer=decode_mariadb_hex_text(row[3]).strip(),
                security_type=decode_mariadb_hex_text(row[4]).strip().upper(),
                sql_data_access=decode_mariadb_hex_text(row[5]).strip().upper(),
                is_deterministic=str(row[6] or "").strip().upper(),
                return_type=decode_mariadb_hex_text(row[7]).strip(),
                sql_mode=decode_mariadb_hex_text(row[8]).strip(),
                routine_definition=decode_mariadb_hex_text(row[9]).strip(),
            )
        )
    return decoded_rows


def decode_mariadb_routine_parameter_detail_entries(rows: Rows) -> list[MariaDBRoutineParameterDetail]:
    """Decodifica filas detalladas de information_schema.parameters a IR tipado."""
    decoded_rows: list[MariaDBRoutineParameterDetail] = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 8:
            continue
        mode_value = row[0]
        name_value = row[1]
        decoded_rows.append(
            MariaDBRoutineParameterDetail(
                mode=(
                    str(mode_value)
                    if str(mode_value) == "RETURN"
                    else decode_mariadb_hex_text(mode_value).strip().upper()
                ),
                name=(
                    str(name_value)
                    if str(name_value) == "RETURN_VALUE"
                    else decode_mariadb_hex_text(name_value).strip()
                ),
                routine_type=str(row[2] or "").strip().upper(),
                routine_name=decode_mariadb_hex_text(row[3]).strip(),
                data_type=decode_mariadb_hex_text(row[4]).strip(),
                charset=decode_mariadb_hex_text(row[5]).strip(),
                collation=decode_mariadb_hex_text(row[6]).strip(),
                default_value="",
                ordinal_position=int(row[7]) if row[7] is not None else None,
            )
        )
    return decoded_rows


def filter_mariadb_routine_parameter_entries(
    rows: list[MariaDBRoutineParameterDetail], *, routine_name: str, routine_type: str
) -> list[MariaDBRoutineParameterDetail]:
    """Filtra parámetros tipados por rutina y tipo."""
    return [entry for entry in rows if entry.matches(routine_name=routine_name, routine_type=routine_type)]


def build_public_mariadb_routine_parameter_entry_rows(rows: list[MariaDBRoutineParameterDetail]) -> Rows:
    """Convierte parámetros tipados al contrato público actual."""
    return [entry.to_public_row() for entry in rows]


__all__: list[str] = [
    "build_public_mariadb_routine_parameter_entry_rows",
    "decode_mariadb_routine_detail_entries",
    "decode_mariadb_routine_parameter_detail_entries",
    "filter_mariadb_routine_parameter_entries",
]
