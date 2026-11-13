"""``util_bbdd.doc.validate_trace_map`` y mensajes sin rutas (5.7.0, G49 de util_bbdd_web).

Antes, el mapa de trazabilidad solo se validaba al construir ``DatabaseDocumentation`` (con la base de datos ya
conectada) y los mensajes del mapa y de ``markdown.previous`` llevaban la ruta completa del fichero, que una
aplicación web no debe mostrar a sus usuarios.
"""

from __future__ import annotations

import os
import stat
import sys

from pathlib import Path

import pytest

import util_bbdd.doc as doc

from util_bbdd.doc import validate_trace_map
from util_bbdd.doc.infrastructure.renderers.markdown._changes import load_previous
from util_bbdd.exceptions import DocumentationConfigError

pytestmark = pytest.mark.unit

BIG = "<más de 1 MB>"  # marcador: el contenido se genera en el test (en el id del parametrize no cabe)
VALID = '[tables."PEDIDOS"]\ncode = ["src/ventas/pedidos.py#Pedido"]\nrequirements = ["REQ-012"]\n'


def _write(tmp_path: Path, name: str, content: str | bytes) -> Path:
    folder = tmp_path / "carpeta_privada"
    folder.mkdir(exist_ok=True)
    file = folder / name
    if isinstance(content, bytes):
        file.write_bytes(content)
    else:
        file.write_text(content, encoding="utf-8")
    return file


def _message(error: pytest.ExceptionInfo[DocumentationConfigError]) -> str:
    return str(error.value)


def test_public_api() -> None:
    assert "validate_trace_map" in doc.__all__
    assert doc.validate_trace_map is validate_trace_map


@pytest.mark.parametrize("as_path", [True, False])
def test_valid_map_returns_none(tmp_path: Path, as_path: bool) -> None:
    file = _write(tmp_path, "trazas.toml", VALID)

    validate_trace_map(file if as_path else str(file))  # válido: no lanza (devuelve None)


def test_valid_json_map(tmp_path: Path) -> None:
    file = _write(tmp_path, "trazas.json", '{"tables": {"PEDIDOS": {"code": ["src/a.py"]}}}')

    validate_trace_map(file)


def test_all_schema_errors_together_and_only_the_file_name(tmp_path: Path) -> None:
    file = _write(tmp_path, "trazas.toml", '[tables."A"]\ncodigo = ["x"]\n\n[vistas."B"]\ncode = ["y"]\n')

    with pytest.raises(DocumentationConfigError) as error:
        validate_trace_map(file)

    message = _message(error)
    assert "trazas.toml" in message
    assert "codigo" in message and "vistas" in message  # los dos errores, juntos
    assert str(tmp_path) not in message and "carpeta_privada" not in message


@pytest.mark.parametrize(
    ("name", "content", "expected"),
    [
        ("trazas.yaml", VALID, "debe ser .toml o .json"),
        ("trazas.toml", "[tables", "no se puede leer"),
        ("trazas.json", "{no es json", "no se puede leer"),
        ("trazas.toml", b"\xff\xfe no utf-8", "no se puede leer"),
        ("trazas.toml", BIG, "supera"),
    ],
    ids=["extension", "toml", "json", "utf8", "tamano"],
)
def test_read_errors_name_the_file_not_its_path(tmp_path: Path, name: str, content: str | bytes, expected: str) -> None:
    file = _write(tmp_path, name, "x" * 1_000_001 if content == BIG else content)

    with pytest.raises(DocumentationConfigError) as error:
        validate_trace_map(file)

    message = _message(error)
    assert expected in message and name in message
    assert str(tmp_path) not in message and "carpeta_privada" not in message


def test_missing_file_hides_the_path(tmp_path: Path) -> None:
    with pytest.raises(DocumentationConfigError) as error:
        validate_trace_map(tmp_path / "carpeta_privada" / "no_existe.toml")

    message = _message(error)
    assert "no se puede leer (no_existe.toml)" in message
    assert str(tmp_path) not in message and "carpeta_privada" not in message


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="permisos POSIX sin root")  # type: ignore[attr-defined,unused-ignore]
def test_unreadable_file_hides_the_path(tmp_path: Path) -> None:
    file = _write(tmp_path, "trazas.toml", VALID)
    file.chmod(0)
    try:
        with pytest.raises(DocumentationConfigError) as error:
            validate_trace_map(file)
    finally:
        file.chmod(stat.S_IRUSR | stat.S_IWUSR)

    assert str(tmp_path) not in _message(error)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("{no es json", "no se puede leer"),
        ('{"format": "otro"}', "no es un catálogo de util_bbdd"),
        (BIG, "supera"),
    ],
    ids=["json", "formato", "tamano"],
)
def test_previous_errors_hide_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str, expected: str
) -> None:
    from util_bbdd.doc.infrastructure.renderers.markdown import _changes

    monkeypatch.setattr(_changes, "MAX_BYTES", 1_000)  # el límite real (50 MB) no merece un fichero de ese tamaño
    file = _write(tmp_path, "catalog.json", "x" * 1_001 if content == BIG else content)

    with pytest.raises(DocumentationConfigError) as error:
        load_previous(file)

    message = _message(error)
    assert expected in message and "carpeta_privada/catalog.json" in message
    assert str(tmp_path) not in message


def test_previous_without_catalog_names_only_the_folder(tmp_path: Path) -> None:
    folder = tmp_path / "carpeta_privada" / "MARKDOWN"
    folder.mkdir(parents=True)

    with pytest.raises(DocumentationConfigError) as error:
        load_previous(folder)

    message = _message(error)
    assert "no hay catalog.json en MARKDOWN" in message
    assert str(tmp_path) not in message
