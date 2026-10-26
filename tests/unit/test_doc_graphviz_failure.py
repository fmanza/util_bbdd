"""Un diagrama que hace fallar a ``dot`` no aborta la documentación (util_bbdd_web G39, 4.1.0).

``dot.pipe`` lanza ``graphviz.CalledProcessError`` cuando ``dot`` termina mal (p. ej. SIGABRT de Graphviz 2.43 con
``splines=ortho``: ``maze.c: chkSgraph``). No es ``OSError`` ni ``RuntimeError``, las dos excepciones que los renderers
de Word y HTML capturan por diagrama, así que escapaba como ``DocumentationRenderError`` y se perdían todos los
formatos. ``_pipe_graph_bytes`` la convierte ahora en ``RuntimeError``, el contrato que ya documentaba.
"""

from __future__ import annotations

import logging
import sqlite3

from pathlib import Path
from typing import Any

import docx
import pytest

graphviz = pytest.importorskip("graphviz")

from util_bbdd import SyncDatabaseManager  # noqa: E402
from util_bbdd.analysis.graphviz_ext import GraphvizRelationshipGraphExt  # noqa: E402
from util_bbdd.doc import DatabaseDocumentation  # noqa: E402

pytestmark = pytest.mark.unit

STDERR = b"Error: maze.c:313: chkSgraph: Assertion `np->cells[0]' failed.\nmore\n"


def _crash(self: Any, *args: Any, **kwargs: Any) -> bytes:
    raise graphviz.CalledProcessError(-6, ["dot", "-Tsvg"], output=b"", stderr=STDERR)


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    path = tmp_path / "demo.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id));
        """
    )
    con.close()
    return path


def test_dot_crash_becomes_runtime_error_with_a_useful_message() -> None:
    generator = GraphvizRelationshipGraphExt.__new__(GraphvizRelationshipGraphExt)
    generator._captured = None
    generator._prefetched = {}
    generator.logger = logging.getLogger(__name__)

    class _Dot:
        engine = "dot"
        source = "digraph {}"
        pipe = _crash

    with pytest.raises(RuntimeError, match=r"señal 6.*orders.*chkSgraph") as raised:
        generator._pipe_graph_bytes(_Dot(), "svg", "orders")

    assert isinstance(raised.value.__cause__, graphviz.CalledProcessError)


def test_documentation_survives_a_crashing_dot(
    monkeypatch: pytest.MonkeyPatch, sqlite_db: Path, tmp_path: Path
) -> None:
    monkeypatch.setattr(graphviz.Digraph, "pipe", _crash)
    monkeypatch.setattr(GraphvizRelationshipGraphExt, "_render_with_dot", lambda *_: {})  # sin lote: todo por pipe

    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager,
            directorio_salida=tmp_path / "out",
            fichero_salida=Path("demo"),
            imprimir={"tablas": {"imprimir_tablas": True, "columnas": True}, "grafo": {"enabled": True}},
            formatos=["word", "html"],
        ).generate()

    word_text = "\n".join(p.text for p in docx.Document(str(result.outputs["word"])).paragraphs)
    assert "No se pudo generar el diagrama" in word_text
    assert "chkSgraph" in word_text
    assert (result.outputs["html"] / "index.html").is_file()
    assert len(list((result.outputs["html"] / "tables").glob("*.html"))) == 2
