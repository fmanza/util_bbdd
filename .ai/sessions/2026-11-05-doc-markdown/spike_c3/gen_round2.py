"""Ronda 2: aisla nombres hostiles y palabras clave, y prueba candidatos de escape."""

from __future__ import annotations

import json
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gen_cases import comment, er, escape_mermaid_label, hostile_names  # noqa: E402

OUT = Path(__file__).parent / "out" / "harness"
cases: list[dict[str, str]] = []


def add(cid: str, text: str) -> None:
    cases.append({"id": cid, "desc": cid, "expect": "?", "text": text})


for i, n in enumerate(hostile_names):
    add(f"alias_{i:02d}", er(f'e1["{escape_mermaid_label(n)}"] {{', "    INTEGER id PK", "}"))
    add(f"label_{i:02d}", er('e1["a"]', 'e2["b"]', f'e1 ||--o{{ e2 : "{comment(n)}"'))
for i, ch in enumerate(["%", "%{", "{", "}", ":", ";", "'", "#", "#quot;", "&", "<", ">", "|", "`", "\\", "/", "(", ")"]):
    add(f"alias_char_{i:02d}_{ch!r}", er(f'e1["a{ch}b"]'))
for w in ["PK", "FK", "UK", "erDiagram", "end", "style", "classDef", "class", "direction", "accTitle", "title",
          "string", "INTEGER", "u", "o", "x"]:
    add(f"colname_{w}", er('e1["t"] {', f"    INTEGER {w}", "}"))
    add(f"typename_{w}", er('e1["t"] {', f"    {w} col", "}"))
for w in ["end", "style", "erDiagram", "PK", "class"]:
    add(f"entityid_{w}", er(f'{w}["t"]'))
OUT.joinpath("cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
print(len(cases))
