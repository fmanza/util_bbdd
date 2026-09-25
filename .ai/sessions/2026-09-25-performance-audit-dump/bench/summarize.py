#!/usr/bin/env python3
"""Resume los ``results.jsonl`` de ``bench_dump_real.py`` en tablas Markdown (línea base, fases y variantes)."""

from __future__ import annotations

import json
import sys

from pathlib import Path

ORDER = ["postgresql", "mysql", "mariadb", "mssql", "oracle", "sqlite"]
PHASES = ["read", "prep_derived", "write", "counts", "constraints_disable", "constraints_enable", "cleanup",
          "indexes_disable", "indexes_rebuild", "analysis", "reflect", "report"]


def load(*paths: Path) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        if p.exists():
            rows += [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows


def fmt(x: float | None, d: int = 1) -> str:
    return "—" if x is None else f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main(session: Path) -> None:
    base = {r["engine"]: r for r in load(session / "baseline/large/results.jsonl") if r.get("variant") == "baseline"}
    var = load(session / "variants/large/results.jsonl")

    print("## Línea base (large, 3,5M filas)\n")
    print("| Motor | Total (s) | Filas/s | RSS pico (MB) | " + " | ".join(PHASES) + " | Verificación | Identidad |")
    print("|---|" + "---|" * (len(PHASES) + 5))
    for e in ORDER:
        r = base.get(e)
        if not r:
            continue
        ph = r["phases"]
        cells = [fmt(ph.get(p, 0.0), 2) for p in PHASES]
        print(f"| {e} | {fmt(r['total_s'])} | {fmt(r['rows_per_s'], 0)} | {fmt(r['peak_rss_mb'], 0)} | "
              + " | ".join(cells) + f" | {r['verify'].get('ok')} | {r['verify'].get('identity_ok')} |")

    variants = sorted({r["variant"] for r in var}, key=lambda v: ["nocount", "stream", "arraysize", "chunk20k",
                      "prefetch", "ranges4", "indexes", "nocheck", "redump", "combo"].index(v)
                      if v in ["nocount", "stream", "arraysize", "chunk20k", "prefetch", "ranges4", "indexes",
                               "nocheck", "redump", "combo"] else 99)
    print("\n## Variantes: tiempo total en s (Δ frente a línea base) y RSS pico en MB\n")
    print("| Motor | baseline | " + " | ".join(variants) + " |")
    print("|---|---|" + "---|" * len(variants))
    for e in ORDER:
        if e not in base:
            continue
        b = base[e]["total_s"]
        cells = []
        for v in variants:
            r = next((x for x in var if x["engine"] == e and x["variant"] == v), None)
            if r is None or "total_s" not in r:
                cells.append("—")
                continue
            bad = not r.get("verify", {}).get("ok") or any(s != "success" for s in r.get("status", {}).values())
            flag = " ⚠" if bad else ""
            cells.append(f"{fmt(r['total_s'])} ({(r['total_s'] / b - 1) * 100:+.0f} %) · {fmt(r['peak_rss_mb'], 0)}{flag}")
        print(f"| {e} | {fmt(b)} · {fmt(base[e]['peak_rss_mb'], 0)} | " + " | ".join(cells) + " |")
    print("\n⚠ = alguna tabla con estado distinto de `success` o verificación origen/destino fallida.")

    print("\n## Detalle de fases por variante (s)\n")
    print("| Motor | Variante | total | read | prep | write | counts | c_enable | cleanup | idx_off | idx_rebuild |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for e in ORDER:
        for r in [base.get(e)] + [x for x in var if x["engine"] == e]:
            if not r or "phases" not in r:
                continue
            ph = r["phases"]
            vals = [ph.get(k, 0.0) for k in ("read", "prep_derived", "write", "counts", "constraints_enable",
                                             "cleanup", "indexes_disable", "indexes_rebuild")]
            print(f"| {e} | {r['variant']} | {fmt(r['total_s'])} | " + " | ".join(fmt(v, 2) for v in vals) + " |")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
