# AUDIT_CODE — Grupo A

Revisión del diff del grupo A (sin commit) contra `PLAN_GRUPO_A.md`.

## Puertas

| Comando | Resultado |
|---|---|
| `ruff format` / `ruff check src tests` | Limpio (2 C420 de un test corregidos) |
| `mypy src tests/unit/test_protocol_conformance.py` | Sin errores (358 ficheros) |
| `pytest` (shell sin URLs del banco) | **6973 passed, 618 skipped** (`build/logs/grupo_a_pytest.txt`) |
| `scripts/gen_arquitectura_capas.py` | Pasa; sin cambios en la figura (no hay imports nuevos entre paquetes: `analysis → _core` y `comparar → _core` ya existían) |

## Hallazgos

| # | Tipo | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|
| A-1 | Bug (encontrado en la prueba con SQLite) | `analysis/mermaid_er.py` `_group_relations` | SQLite no da nombre a las FK: agrupar por `(padre, hija, restricción)` fundía dos FK distintas y la nulabilidad de una pasaba a la otra | **Corregido**: las FK sin nombre no se agrupan. Test `test_sqlite_end_to_end` |
| A-2 | Deuda heredada (F3) | `analysis/base.py` `_determine_cardinality` | Toda FK **identificante** (columna de la FK dentro de la PK hija, el patrón cabecera-detalle) sale como `M:N` (`}o--o{`), porque se comprueba «columna origen es PK» con una sola columna. Graphviz dibuja lo mismo desde antes. Con FK compuesta o PK compuesta, el resultado es incorrecto: debería ser `1:N` (o `1:1` si la FK es toda la PK) | Paridad mantenida por el plan; fijado por test. **Recomendación: corregirlo en un `fix(analysis)` aparte**, porque cambia también Graphviz |
| A-3 | Deuda heredada | `_build_cardinality_markers` con `N:1` | FK que apunta a una columna que no es PK: la «N» queda en el lado padre (`}o..o\|`) | Paridad mantenida; registrado |
| A-4 | Diseño | `mermaid_er.py` `_attributes` | Con `max_columns` bajo, en `relations` pueden quedar fuera columnas FK dibujadas | Aceptado (mismo criterio que Graphviz). Documentar en el grupo F |
| A-5 | Seguridad | `_core/mermaid.py` | `<script>` en un alias se emite tal cual dentro del texto Mermaid; Mermaid con `securityLevel: "strict"` lo muestra como texto (SPIKE_C3). El renderer del grupo B lo pone dentro de una *fence*, nunca como HTML | Aceptado |
| A-6 | Rendimiento | `_relation_line` | Lee `snapshot.columns(hija)` y la PK por relación: lecturas del snapshot ya cacheado, O(relaciones × columnas) | Aceptado |

## Tipado y contratos

- `_split_relations_for_visualization` pasa a ser genérica (`[R]`, PEP 695); los llamadores existentes no cambian.
- LSP: los métodos movidos conservan firma; los tests que los sustituyen en instancias de Graphviz siguen en verde.

## Veredicto

**APROBADO**, con A-2 propuesto como corrección aparte (decisión del usuario).
