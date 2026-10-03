"""Tablas Markdown del baseline a partir de ``results/*.json`` (una tabla por flujo: motor × volumen).

Celda: ``consultas de catálogo · tiempo de catálogo s / tiempo total s``. En 5000 tablas, ``manager_scan`` recorre
una muestra (``limit``) y se indica.

    python report_baseline.py > tablas.md
"""

from __future__ import annotations

import json

from pathlib import Path

RESULTS = Path(__file__).parent / "results"
ENGINES = ("sqlite", "postgresql", "mysql", "mariadb", "sqlserver", "oracle")
VOLUMES = (50, 500, 5000)
FLOWS = ("manager_scan", "doc_html", "comparar", "migrate", "migrate_extract", "dump", "bulk")


def _cell(d: dict | None) -> str:
    if d is None:
        return "—"
    if d.get("info", {}).get("skipped"):
        return "n/a"
    if d.get("error"):
        return f"error: {d['error'][:40]}"
    sample = f" (muestra {d['limit']})" if d.get("limit") else ""
    return f"{d['queries_catalog']:,} · {d['median_catalog_seconds']:.2f} / {d['median_seconds']:.2f} s{sample}".replace(",", ".")


def main() -> None:
    data = {}
    for f in RESULTS.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        data[(d["flow"], d["engine"], d["volume"])] = d
    for flow in FLOWS:
        if not any(k[0] == flow for k in data):
            continue
        print(f"\n#### `{flow}`\n")
        print("| Motor | 50 tablas | 500 tablas | 5000 tablas |")
        print("|---|---|---|---|")
        for engine in ENGINES:
            cells = [_cell(data.get((flow, engine, v))) for v in VOLUMES]
            if all(c == "—" for c in cells):
                continue
            print(f"| {engine} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
