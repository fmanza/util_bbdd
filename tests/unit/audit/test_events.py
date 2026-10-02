"""``AuditEvent``: inmutable, con zona horaria y saneado del texto libre."""

from __future__ import annotations

import dataclasses
import json

from datetime import UTC, datetime, timedelta, timezone

import pytest

from util_bbdd.audit import AuditEvent


def _event(**fields: object) -> AuditEvent:
    base: dict[str, object] = {"source": "bulk", "kind": "operation", "status": "ok", "timestamp": datetime.now(UTC)}
    base.update(fields)
    return AuditEvent(**base)  # type: ignore[arg-type]


def test_now_usa_utc_y_atributos_ordenados() -> None:
    event = AuditEvent.now(source="dump", kind="table", status="ok", attributes={"z": 1, "a": "x"})

    assert event.timestamp.tzinfo is UTC
    assert event.attributes == (("a", "x"), ("z", 1))
    assert event.attribute("z") == 1
    assert event.attribute("nada") is None


def test_es_inmutable_y_hashable() -> None:
    event = _event(rows=3)

    with pytest.raises(dataclasses.FrozenInstanceError):
        event.rows = 4  # type: ignore[misc]
    assert hash(event) == hash(_event(rows=3, timestamp=event.timestamp))


def test_rechaza_timestamp_sin_zona() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        _event(timestamp=datetime(2026, 10, 2, 12, 0))


@pytest.mark.parametrize(("field", "value"), [("rows", -1), ("elapsed_s", -0.1)])
def test_rechaza_negativos(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=field):
        _event(**{field: value})


def test_rechaza_atributos_repetidos() -> None:
    with pytest.raises(ValueError, match="repetidos"):
        _event(attributes=(("a", 1), ("a", 2)))


def test_message_en_una_linea_y_truncado() -> None:
    event = _event(message="línea 1\r\nlínea 2\tcon tabulador")
    assert event.message == "línea 1 línea 2 con tabulador"

    largo = _event(message="x" * 1000)
    assert largo.message is not None
    assert len(largo.message) == AuditEvent.MAX_MESSAGE
    assert largo.message.endswith("…")


def test_as_dict_es_serializable_con_zona() -> None:
    event = _event(
        timestamp=datetime(2026, 10, 2, 12, 0, tzinfo=timezone(timedelta(hours=2))),
        target="t",
        attributes=(("batch_size", 500),),
    )

    data = json.loads(json.dumps(event.as_dict()))

    assert data["timestamp"] == "2026-10-02T12:00:00+02:00"
    assert data["attributes"] == {"batch_size": 500}
    assert data["target"] == "t"
