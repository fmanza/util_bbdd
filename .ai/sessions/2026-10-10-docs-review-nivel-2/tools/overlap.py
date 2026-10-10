"""Solapamiento entre páginas: Jaccard de shingles de 6 palabras (sin bloques de código ni tablas de cabecera fija)."""

import itertools
import re
import sys
from pathlib import Path

pending = set(Path(sys.argv[1]).read_text(encoding="utf-8").split())
pages = [
    p.as_posix()
    for p in Path("docs").rglob("*.md")
    if "v0.8.0" not in p.parts and "adr" not in p.parts
]
BOILER = re.compile(r"^(#|\|[-| ]+\||\*No aplica)")


def shingles(path: str) -> set[tuple[str, ...]]:
    words: list[str] = []
    in_code = False
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_code = not in_code
            continue
        if in_code or BOILER.match(line.strip()):
            continue
        words += re.findall(r"\w+", line.lower())
    return {tuple(words[i : i + 6]) for i in range(len(words) - 5)}


sh = {p: shingles(p) for p in pages}
rows = []
for a, b in itertools.combinations(pages, 2):
    if a not in pending and b not in pending:
        continue
    sa, sb = sh[a], sh[b]
    if not sa or not sb:
        continue
    inter = len(sa & sb)
    contain = inter / min(len(sa), len(sb))
    if contain >= 0.12:
        rows.append((contain, inter, a, b))
for c, i, a, b in sorted(rows, reverse=True):
    print(f"{c:5.2f} {i:5d}  {a}  <->  {b}")
