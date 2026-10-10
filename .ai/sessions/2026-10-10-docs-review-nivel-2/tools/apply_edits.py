"""Aplica sustituciones exactas desde un JSON: [{"file": ..., "old": ..., "new": ...}, ...].

Cada `old` debe aparecer exactamente una vez (o `count` veces si se indica); si no, no se escribe nada.
Uso: python apply_edits.py edits.json
"""

import json
import sys
from pathlib import Path

edits = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
texts: dict[str, str] = {}
errors = []
for e in edits:
    f = e["file"]
    texts.setdefault(f, Path(f).read_text(encoding="utf-8"))
    n = texts[f].count(e["old"])
    want = e.get("count", 1)
    if n != want:
        errors.append(f"{f}: {n} apariciones (se esperaban {want}) de {e['old'][:70]!r}")
        continue
    texts[f] = texts[f].replace(e["old"], e["new"])
if errors:
    print("\n".join(errors))
    sys.exit(1)
for f, t in texts.items():
    eol = "\r\n" if b"\r\n" in Path(f).read_bytes() else "\n"  # conserva el fin de línea de la copia de trabajo
    Path(f).write_text(t, encoding="utf-8", newline=eol)
print(f"{len(edits)} sustituciones en {len(texts)} ficheros")
