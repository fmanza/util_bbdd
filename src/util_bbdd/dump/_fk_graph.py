"""Grafo de dependencias FK y orden de carga (topológico, por niveles y ciclos) del volcado.

Separado de ``orchestrator`` (R10a del refactor de reutilización 2026-09-26) sin cambios de comportamiento;
``DumpOrchestrator`` conserva los métodos estáticos (``_topological_sort``…) como delegados.
"""

from __future__ import annotations

import logging

from collections import deque

from sqlalchemy import Engine, Inspector, text
from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.metadata.sqlserver.constraints import fetch_schema_fk_references_sql

# Mismo logger que antes de separar este código de ``orchestrator`` (R10a): los registros no cambian de nombre.
_log = logging.getLogger("util_bbdd.dump.orchestrator")


def build_fk_graph(
    tables: list[str],
    inspector: Inspector,
    schema: str | None,
) -> tuple[dict[str, set[str]], dict[str, int]]:
    """Construye el grafo de dependencias FK entre las tablas dadas."""
    tables_set = set(tables)
    # dependents[A] = {B} → B depende de A (A debe cargarse antes que B)
    dependents: dict[str, set[str]] = {t: set() for t in tables}
    in_degree: dict[str, int] = dict.fromkeys(tables, 0)

    for table, refs in referred_tables(tables, inspector, schema).items():
        for referred in refs:
            if referred and referred != table and referred in tables_set and table not in dependents[referred]:
                dependents[referred].add(table)
                in_degree[table] += 1

    return dependents, in_degree


def referred_tables(tables: list[str], inspector: Inspector, schema: str | None) -> dict[str, list[str]]:
    """Tabla → tablas referidas por sus FK (una por FK). Las tablas cuya introspección falla no aparecen.

    Q9 (performance-audit de dump 2026-09-26): en SQL Server, ``get_foreign_keys`` hace una consulta por tabla de
    ≈ 34 ms (61 % de un volcado de 200 tablas pequeñas); allí se lee todo el schema con una consulta. Si esa
    consulta falla, se vuelve a la introspección tabla a tabla.
    """
    if inspector.dialect.name == "mssql":
        by_table = mssql_referred_tables(inspector, schema)
        if by_table is not None:
            by_lower = {name.lower(): refs for name, refs in by_table.items()}
            # Nombres dados por el usuario (DumpConfig.tables) con otro case: SQL Server suele ser case-insensitive.
            return {t: by_table.get(t, by_lower.get(t.lower(), [])) for t in tables}
    referred: dict[str, list[str]] = {}
    for table in tables:
        try:
            fks = inspector.get_foreign_keys(table, schema=schema)
        except SQLAlchemyError:
            continue
        referred[table] = [fk.get("referred_table") or "" for fk in fks]
    return referred


def mssql_referred_tables(inspector: Inspector, schema: str | None) -> dict[str, list[str]] | None:
    """SQL Server: tablas referidas por las FK de cada tabla del schema, en una consulta. ``None`` si falla."""
    bind = inspector.bind
    if not isinstance(bind, Engine):
        return None
    try:
        with bind.connect() as conn:
            rows = conn.execute(
                text(fetch_schema_fk_references_sql()), {"schema": schema or inspector.default_schema_name}
            ).all()
    except SQLAlchemyError as exc:
        _log.debug("Consulta de FK por schema falló (%s); se usa get_foreign_keys tabla a tabla.", exc)
        return None
    by_table: dict[str, list[str]] = {}
    for table, _ref_schema, ref_table in rows:
        by_table.setdefault(table, []).append(ref_table)
    return by_table


def topological_levels(
    tables: list[str],
    inspector: Inspector,
    schema: str | None,
) -> list[list[str]]:
    """Agrupa las tablas en niveles topológicos FK (Kahn por profundidad).

    Cada nivel contiene tablas mutuamente independientes (sin FK entre ellas),
    cargables concurrentemente. Las tablas en ciclos FK se excluyen (no aparecen
    en ningún nivel). Dentro de cada nivel el orden es alfabético (determinista).
    """
    dependents, in_degree = build_fk_graph(tables, inspector, schema)
    levels: list[list[str]] = []
    seen: set[str] = set()
    current: list[str] = sorted(t for t in tables if in_degree[t] == 0)

    while current:
        levels.append(current)
        seen.update(current)
        nxt: set[str] = set()
        for node in current:
            for dep in dependents[node]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    nxt.add(dep)
        current = sorted(nxt)

    return levels


def topological_sort(
    tables: list[str],
    inspector: Inspector,
    schema: str | None,
) -> tuple[list[str], list[list[str]]]:
    """Ordena tablas respetando dependencias FK usando el algoritmo de Kahn.

    Returns:
        (ordered_tables, cycles) — las tablas en ciclos se añaden al final
        de ``ordered_tables`` y se listan en ``cycles``.
    """
    dependents, in_degree = build_fk_graph(tables, inspector, schema)

    queue: deque[str] = deque(t for t in tables if in_degree[t] == 0)
    ordered: list[str] = []

    while queue:
        node = queue.popleft()
        ordered.append(node)
        for dep in sorted(dependents[node]):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    cycle_tables = [t for t in tables if t not in set(ordered)]
    if not cycle_tables:
        return ordered, []

    cycles = find_cycle_components(cycle_tables, dependents)
    return ordered + cycle_tables, cycles


def find_cycle_components(
    cycle_tables: list[str],
    dependents: dict[str, set[str]],
) -> list[list[str]]:
    """Agrupa nodos en ciclo FK en componentes conexas mediante BFS no dirigido."""
    adj = build_cycle_adj(cycle_tables, dependents)
    visited: set[str] = set()
    cycles: list[list[str]] = []
    for start in cycle_tables:
        if start not in visited:
            component = bfs_component(start, adj, visited)
            cycles.append(component)
    return cycles


def build_cycle_adj(
    cycle_tables: list[str],
    dependents: dict[str, set[str]],
) -> dict[str, set[str]]:
    """Construye grafo de adyacencia no dirigido restringido a los nodos en ciclo."""
    cycle_set = set(cycle_tables)
    adj: dict[str, set[str]] = {t: set() for t in cycle_tables}
    for node, deps in dependents.items():
        if node not in cycle_set:
            continue
        for dep in deps:
            if dep in cycle_set:
                adj[node].add(dep)
                adj[dep].add(node)
    return adj


def bfs_component(
    start: str,
    adj: dict[str, set[str]],
    visited: set[str],
) -> list[str]:
    """Retorna todos los nodos alcanzables desde ``start`` mediante BFS."""
    component: list[str] = []
    queue: deque[str] = deque([start])
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        component.append(node)
        queue.extend(n for n in adj[node] if n not in visited)
    return component
