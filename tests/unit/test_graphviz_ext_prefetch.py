"""Precarga por lotes de renders Graphviz (P-01) y nombres de fichero seguros (S-04)."""

from __future__ import annotations

import logging
import threading

from pathlib import Path
from typing import Any

import pytest

import util_bbdd.analysis.graphviz_ext as module

from util_bbdd.analysis.graphviz_ext import GraphvizRelationshipGraphExt


class _FakeDot:
    """Grafo mínimo: fuente DOT, motor y un ``pipe`` (el render grafo a grafo) que cuenta llamadas."""

    encoding = "utf-8"

    def __init__(self, source: str, pipes: dict[str, int], lock: threading.Lock, engine: str = "dot") -> None:
        self.source = source
        self.engine = engine
        self._pipes = pipes
        self._lock = lock

    def pipe(self, format: str) -> bytes:
        with self._lock:
            self._pipes[self.source] = self._pipes.get(self.source, 0) + 1
        if "FAIL" in self.source:
            raise RuntimeError(f"dot falló para {self.source}")
        return f"{format}:{self.source}".encode()


class _FakeDotProcess:
    """Sustituye a ``subprocess.run(["dot", "-K…", "-T…", "-O", ficheros…])``: escribe ``<fichero>.<formato>``."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self._lock = threading.Lock()

    def __call__(self, command: list[str], cwd: str, **_: Any) -> None:
        with self._lock:
            self.commands.append(command)
        format_ = command[2].removeprefix("-T")
        for name in command[4:]:
            source = Path(cwd, name).read_text(encoding="utf-8")
            if "FAIL" not in source:  # dot no escribe la salida de un grafo con error
                Path(cwd, f"{name}.{format_}").write_bytes(f"{format_}:{source}".encode())


@pytest.fixture
def dot_process(monkeypatch: pytest.MonkeyPatch) -> _FakeDotProcess:
    fake = _FakeDotProcess()
    monkeypatch.setattr(module.subprocess, "run", fake)
    return fake


def _generator(workers: int) -> GraphvizRelationshipGraphExt:
    graph = object.__new__(GraphvizRelationshipGraphExt)
    graph.logger = logging.getLogger(__name__)
    graph.render_workers = workers
    graph._prefetched = {}
    graph._captured = None
    graph._parent_relations_index_by_context = {}
    graph._graph_document_cache_by_context = {}
    graph._table_visual_type_cache_by_context = {}
    return graph


def _render_factory(graph: GraphvizRelationshipGraphExt, pipes: dict[str, int], fmt: str = "svg") -> Any:
    lock = threading.Lock()

    def render(table_name: str) -> bytes:
        engine = "circo" if table_name.startswith("c_") else "dot"
        dot = _FakeDot(f"digraph {table_name}", pipes, lock, engine=engine)
        return graph._pipe_graph_bytes(dot=dot, format=fmt, table_name=table_name)

    return render


def test_prefetch_renders_in_few_dot_processes_and_real_calls_reuse_it(dot_process: _FakeDotProcess) -> None:
    graph = _generator(workers=2)
    pipes: dict[str, int] = {}
    render = _render_factory(graph, pipes)

    rendered = graph.prefetch(render, ["a", "b", "c", "d", "e", "a"])

    assert rendered == 5  # "a" repetida: una sola clave
    assert len(dot_process.commands) == 2  # un proceso dot por lote, no uno por grafo
    assert all(command[1:4] == ["-Kdot", "-Tsvg", "-O"] for command in dot_process.commands)
    assert render("b") == b"svg:digraph b"
    assert render("a") == b"svg:digraph a"
    assert pipes == {}  # ningún render grafo a grafo


def test_prefetch_groups_batches_by_engine(dot_process: _FakeDotProcess) -> None:
    graph = _generator(workers=8)
    render = _render_factory(graph, {}, fmt="png")

    graph.prefetch(render, ["a", "c_b"])

    assert sorted(command[1] for command in dot_process.commands) == ["-Kcirco", "-Kdot"]
    assert render("c_b") == b"png:digraph c_b"


def test_prefetch_capture_does_not_return_real_bytes(dot_process: _FakeDotProcess) -> None:
    graph = _generator(workers=2)
    captured: list[bytes] = []
    render = _render_factory(graph, {})

    graph.prefetch(lambda table_name: captured.append(render(table_name)), ["a"])

    assert captured == [b""]


def test_prefetch_with_one_worker_still_batches(dot_process: _FakeDotProcess) -> None:
    graph = _generator(workers=1)
    render = _render_factory(graph, {})

    assert graph.prefetch(render, ["a", "b", "c"]) == 3
    assert len(dot_process.commands) == 1


def test_failed_graph_is_rendered_alone_and_its_error_reaches_the_real_call(dot_process: _FakeDotProcess) -> None:
    graph = _generator(workers=2)
    pipes: dict[str, int] = {}
    render = _render_factory(graph, pipes)

    graph.prefetch(render, ["ok", "FAIL"])

    assert render("ok") == b"svg:digraph ok"
    with pytest.raises(RuntimeError, match="digraph FAIL"):
        render("FAIL")
    assert pipes == {"digraph FAIL": 1}  # solo el fallido se renderizó aparte


def test_prefetch_falls_back_to_one_pipe_per_graph_without_dot(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing_dot(*_: Any, **__: Any) -> None:
        raise FileNotFoundError("dot")

    monkeypatch.setattr(module.subprocess, "run", _missing_dot)
    graph = _generator(workers=2)
    pipes: dict[str, int] = {}
    render = _render_factory(graph, pipes)

    graph.prefetch(render, ["a", "b"])

    assert render("a") == b"svg:digraph a"
    assert pipes == {"digraph a": 1, "digraph b": 1}


def test_prefetch_replaces_previous_batch_and_clear_cache_drops_it(dot_process: _FakeDotProcess) -> None:
    graph = _generator(workers=2)
    pipes: dict[str, int] = {}
    render = _render_factory(graph, pipes)

    graph.prefetch(render, ["a"])
    graph.prefetch(render, ["b"])
    render("a")  # ya no está precargada: render grafo a grafo
    assert pipes == {"digraph a": 1}

    graph.clear_cache()
    render("b")
    assert pipes == {"digraph a": 1, "digraph b": 1}


def test_disk_variants_use_a_safe_file_name(tmp_path: Path) -> None:
    graph = _generator(workers=1)
    graph.pipe_paginated_graph_ext = lambda **kwargs: [b"p1", b"p2"]  # type: ignore[method-assign]

    paths = graph.generate_graphviz_graph_paginated_ext(
        table_name="../../evil/Ta ble", output_dir=tmp_path / "out", format="svg"
    )

    assert [p.name for p in paths] == ["graphviz_ext_evil-ta-ble_page1.svg", "graphviz_ext_evil-ta-ble_page2.svg"]
    assert all(p.parent == (tmp_path / "out").resolve() for p in paths)
