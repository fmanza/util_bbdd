"""``SchemaSnapshot.routine_parameters`` indexado (F7, v0.42.0): mismo resultado que el recorrido lineal anterior."""

from __future__ import annotations

import pytest

from util_bbdd.metadata.model import (
    Kind,
    KindNotLoadedError,
    RoutineKey,
    RoutineMeta,
    RoutineParameterMeta,
    SchemaSnapshot,
)


def _param(name: str, signature: str, routine_type: str, ordinal: int) -> RoutineParameterMeta:
    return RoutineParameterMeta(RoutineKey(name, signature, routine_type), ordinal, f"p{ordinal}", "IN", "integer")


PARAMS = (
    _param("f", "integer", "FUNCTION", 1),
    _param("f", "text", "FUNCTION", 1),  # sobrecarga
    _param("p", "", "PROCEDURE", 2),
    _param("p", "", "PROCEDURE", 1),  # el orden de lectura se conserva
    _param("p", "", "FUNCTION", 1),  # mismo nombre, otro tipo (Oracle, SQL Server)
)
SNAPSHOT = SchemaSnapshot(
    "oracle", "S", {Kind.ROUTINES: (RoutineMeta("f", "FUNCTION"),), Kind.ROUTINE_PARAMETERS: PARAMS}
)


@pytest.mark.parametrize(
    "key",
    [
        RoutineKey("f", "integer"),
        RoutineKey("f", "text", "FUNCTION"),
        RoutineKey("p", "", "PROCEDURE"),
        RoutineKey("p"),  # sin tipo: los de cualquier tipo
        RoutineKey("missing"),
    ],
)
def test_same_result_as_scanning_all_parameters(key: RoutineKey) -> None:
    assert SNAPSHOT.routine_parameters(key) == tuple(p for p in PARAMS if p.routine.matches(key))


def test_requires_routine_parameters_loaded() -> None:
    with pytest.raises(KindNotLoadedError):
        SchemaSnapshot("oracle", "S", {Kind.ROUTINES: ()}).routine_parameters(RoutineKey("f"))
