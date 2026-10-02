# Prompt: audit_module — módulo de auditoría centralizado

> **Ejecutado en v0.29.0** (ADR-002; sesiones `.ai/sessions/2026-10-02c-audit-module/` y
> `2026-10-02d-audit-hardening/`). Se conserva como referencia del método: el inventario de partida describe el estado
> de v0.28.0 (rutas anteriores al traslado a `util_bbdd.audit`). No lo reejecutes tal cual; para evolucionar la
> auditoría usa `/new-feature` sobre `src/util_bbdd/audit/` y `docs/api/audit.md`.

Diseñar e implementar, por fases, un paquete nuevo de auditoría que centralice la que hoy está
repartida entre `bulk/`, `dump/` y `migrate/`. Es un `new_feature` con extracción controlada de
código existente: aplica el contrato de [`new_feature.prompt.md`](new_feature.prompt.md) más las
secciones y reglas adicionales de este prompt. Si discrepan, manda este prompt.

Agentes: Plan Architect (PLAN + AUDIT_PLAN) → Feature Implementer (IMPLEMENT) → Code Auditor
(AUDIT_CODE) → Version Closer (VERSION). Security Reviewer revisa el AUDIT_PLAN (ver § Seguridad).

---

## Contexto obligatorio

Lee, en este orden, antes de emitir PLAN:

1. [`.ai/audit/audit_module_baseline_inventory.md`](../../.ai/audit/audit_module_baseline_inventory.md)
   — **línea base mínima** (`INV-*`) y huecos observados (`H-*`).
2. `.github/instructions/architecture.instructions.md` § Regla #6 (capas) y § «Evidencia mínima en
   cambios arquitectónicos».
3. `.github/instructions/python.instructions.md` y `.github/instructions/tests.instructions.md`.
4. `docs/functional/bulk_audit.md` y `docs/api/bulk_audit.md` (lo que el usuario ya conoce).
5. El código real de cada `INV-*`: **re-verifica las rutas y cita `archivo:línea` del árbol actual**;
   el inventario es una foto fechada.

Puedes consultar internet para normas y buenas prácticas; cita la URL en el PLAN. Referencias de
partida (no obligatorias, no inventes otras sin consultarlas):

- OpenTelemetry, *Semantic conventions for database client spans* —
  <https://opentelemetry.io/docs/specs/semconv/database/database-spans/> (`db.system.name`,
  `db.namespace`, `db.collection.name`, `db.operation.name`, `db.operation.batch.size`,
  `db.response.returned_rows`, `error.type`; `db.query.text` solo si está saneado).
- OWASP *Logging Cheat Sheet* — <https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html>
  (cuándo/dónde/quién/qué; datos que nunca se registran; integridad e inyección en logs).
- OWASP *CSV Injection* — <https://owasp.org/www-community/attacks/CSV_Injection>.

---

## Inputs requeridos

| Input | Valor por defecto si el usuario no lo da |
|---|---|
| **Nombre del paquete** | `src/util_bbdd/audit/` |
| **Capa (Regla #6)** | La decide el PLAN; debe ser ≤ 5 (lo consumen `bulk`=6, `migrate`=6, `dump`=7) |
| **Fases a ejecutar en esta sesión** | Solo PLAN + AUDIT_PLAN |
| **Política de compatibilidad** | Sin breaking changes en `0.x` actual: API pública y formato CSV idénticos; deprecaciones con aviso |
| **Ámbito de consumidores** | Solo `bulk/`, `dump/`, `migrate/` (el resto de paquetes queda fuera) |
| **Nuevas capacidades** | Las que el PLAN proponga desde los huecos `H-*`, siempre opt-in |
| **Dependencias nuevas** | Ninguna (pandas, openpyxl y stdlib ya están) |

Si el usuario no da un input, aplica el valor por defecto y decláralo como supuesto en el PLAN.
Si un input contradice una regla de este prompt, detente y pregunta.

---

## Objetivo y alcance

**Objetivo**: un único punto canónico para registrar, persistir, leer, resumir y exportar la
auditoría de las operaciones de `bulk`, `dump` y `migrate`, con un modelo de evento común y
contratos tipados, sin cambiar el comportamiento observable actual.

**Dentro**: todo lo listado en `INV-BLK-*`, `INV-REJ-*`, `INV-DMP-*`, `INV-MIG-*` e `INV-X-*`.

**Fuera** (no proponer ni tocar): `comparar/`, `doc/`, `managers/`, `metadata/`, `analysis/`;
envío a servicios externos (OpenTelemetry exporter, SIEM, colas); persistencia en tablas de BD;
cambios de rendimiento no exigidos por la centralización.

---

## Reglas de diseño (no negociables)

1. **Cobertura mínima**: cada `INV-*` acaba en una de tres situaciones, y el PLAN lo dice en la
   matriz de cobertura: *centralizado* (con su destino), *se queda en el módulo de origen* (con
   motivo: p. ej. `Isolator` es lógica de ejecución, no de auditoría) o *adaptado* (el origen lo
   convierte en eventos del módulo nuevo). Ningún `INV-*` sin decisión.
2. **Dirección de dependencias**: el paquete nuevo **no importa** `bulk`, `dump` ni `migrate`
   (tampoco bajo `TYPE_CHECKING` ni de forma perezosa). Los tipos propios de cada módulo
   (`MigrationWarning`, `TableDumpResult`, `PartitionResult`…) se convierten a eventos genéricos
   **en el módulo de origen** mediante adaptadores. Solo puede importar de capas inferiores
   (`_core` para excepciones).
3. **Contratos antes que implementaciones** (Regla #4): `Protocol` para el destino de eventos
   (*sink*) y para la lectura; al menos tres implementaciones: CSV compatible con el formato
   actual, nula (auditoría deshabilitada) y en memoria (tests). Todo `Protocol` nuevo entra en
   `tests/unit/test_protocol_conformance.py`.
4. **Compatibilidad byte a byte del CSV actual** (`INV-BLK-03`): mismas columnas, orden,
   separador, formato de fecha, coma decimal y `Sí`/`No`. Un formato mejorado (zona horaria,
   punto decimal, id de correlación, JSON Lines…) solo como sink **nuevo y opt-in**.
5. **API pública intacta**: `AuditManager`, `BulkCrud(audit_*=…)`, `ParallelBulkLoader`,
   `DumpConfig.bulk_audit_*`, `DumpAuditSummary`, `DumpReporter`, `MigrationWarning`,
   `MigrationPlan.execute` y las excepciones `Audit*` conservan nombre, firma, import y semántica.
   `bulk/audit.py` pasa a ser fachada/re-exportador del paquete nuevo si el PLAN lo decide.
6. **Excepciones**: siguen en `_core/exceptions.py` (jerarquía canónica). No dupliques clases.
7. **Semántica preservada**: `rowcount` = filas enviadas (`INV-BLK-04`); política
   `audit_strict` y sus cuatro contadores (`INV-BLK-14/15`); auditoría diferida al commit
   (`INV-BLK-13`); invariante de conciliación de `ParallelLoadResult` (`INV-BLK-17`); un aviso por
   instancia o por volcado (`INV-BLK-06`, `INV-DMP-02`); el volcado no aborta si falla el resumen
   (`INV-DMP-10`); `execute` bloqueado con avisos `ERROR` (`INV-MIG-04`).
8. **Concurrencia**: el lock por ruta pasa a ser API interna pública del paquete (sin `_` cruzado
   entre módulos: resuelve `H-06`). El alcance sigue siendo intra-proceso salvo que el PLAN
   justifique otra cosa y su coste.
9. **Modelo de evento**: un `dataclass(frozen=True, slots=True)` con, como mínimo, cuándo
   (`timestamp` con zona), dónde (motor, esquema/namespace, tabla/objeto), qué (origen
   `bulk`/`dump`/`migrate`, tipo de evento, operación), resultado (estado, filas, duración,
   `error.type`) y correlación (`run_id`/`parent_id`). Nombres en el idioma del código del
   proyecto; documenta su equivalencia con OpenTelemetry sin acoplarte a su SDK.
10. **Nuevas capacidades** (desde `H-*`): opt-in, desactivadas por defecto, una por fase, con
    tests y documentación. Prioridad orientativa: correlación (`H-02`) → rastro de `migrate`
    (`H-03`) → formato nuevo (`H-04`). Cada una con su `INV`/`H` de origen.
11. **Estilo del proyecto**: clases con `self.logger`, f-strings, `ClassVar` para constantes,
    sin `print()`, sin estado global mutable (el registro de locks por ruta es la única excepción
    existente: no añadas otras), docstrings Google-style con ejemplo en lo público.
12. **No mezclar**: nada de refactors ajenos a la centralización ni de optimizaciones de
    rendimiento; si aparecen, van al backlog del VERSION.

## Seguridad

- Nunca registrar credenciales, cadenas de conexión ni `conn_params`.
- Valores de filas solo en el CSV de rechazos y solo con ruta explícita del usuario (`INV-REJ-01`).
- Neutralización de fórmulas (`INV-REJ-02`) en **todo** sink tabular (CSV, Excel); escape en HTML;
  eliminación de CR/LF y del separador en campos de texto libre (OWASP).
- Texto SQL: no se registra; si el PLAN lo propone, solo saneado (literales → `?`) y opt-in.
- Verifica y cierra `H-07` (es un hallazgo potencial: confírmalo con `archivo:línea` o descártalo).

---

## Devuelve en este orden

### PLAN

- supuestos (inputs por defecto aplicados)
- **matriz de cobertura** `INV-*` → {centralizado | se queda | adaptado} + destino + motivo
- decisión sobre cada hueco `H-*` (incorporar en fase N | descartar + motivo)
- estructura del paquete (ficheros, responsabilidades, una línea cada uno)
- capa asignada y cambios en `LAYER`/`DRAWN` de `scripts/gen_arquitectura_capas.py` y en
  `.ai/architecture.md`
- contratos (`Protocol`/dataclasses) con firmas tipadas
- adaptadores por módulo de origen (qué tipo convierten y dónde viven)
- **plan de fases incremental**, cada una entregable y con la suite verde:
  - F0 núcleo (modelo, contratos, sinks, lock por ruta) sin consumidores;
  - F1 `bulk` adopta el núcleo (CSV byte a byte idéntico) y `AuditManager` pasa a fachada;
  - F2 rechazos;
  - F3 `dump` (resumen e informe sin cambios visibles);
  - F4 `migrate` (adaptador de avisos; rastro de ejecución opt-in si se aprobó `H-03`);
  - F5 capacidades opt-in aprobadas, deprecaciones y documentación.
  Puedes reordenar o fusionar fases si lo justificas.
- borrador de **ADR** (`docs/adr/ADR-NNN-modulo-auditoria.md`, desde `docs/adr/ADR-TEMPLATE.md`):
  patrón elegido, alternativa descartada, consecuencias
- referencias externas consultadas (URL)
- riesgos

### AUDIT_PLAN

- riesgos funcionales (semántica de contadores, conciliación, auditoría diferida)
- riesgos técnicos (Regla #6, LSP de los sinks, sync/async, hilos)
- riesgos de seguridad (§ Seguridad; lo revisa Security Reviewer)
- riesgos de compatibilidad (imports, pickling, formato CSV, mensajes de log en tests)
- coste de rendimiento estimado por evento frente al actual (sin optimizar: solo no empeorar;
  umbral orientativo ≤ 5 % en la ruta caliente de `bulk`)
- simplificaciones posibles
- **Veredicto:** `GO | NO_GO | GO_CONDICIONAL` (con condiciones)

Detente aquí y espera aprobación explícita (y de qué fases) antes de IMPLEMENT.

### IMPLEMENT (una fase aprobada por iteración)

- cambios por archivo, código y explicación breve (Level 1 → 2 → 3)
- tests nuevos: contrato de cada `Protocol` (sustitución de implementaciones), compatibilidad
  byte a byte del CSV (fichero de referencia generado con la versión anterior), concurrencia
  (varios hilos sobre la misma ruta), y los de cada capacidad nueva
- `INV-X-03`: los tests existentes pasan **sin modificarlos**; si alguno debe cambiar (solo
  imports privados), lístalo y justifícalo
- comandos de `SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo» en verde, más
  `python scripts/gen_arquitectura_capas.py` y `tests/unit/test_architecture_import_rules.py`

### AUDIT_CODE

Contrato de `new_feature` (bugs `archivo:línea`, edge cases, performance, seguridad, tipado,
deuda técnica) **más**:

- matriz de cobertura re-verificada: estado real de cada `INV-*` tras la fase
- imports del paquete nuevo hacia capas superiores (debe ser ninguno)
- diff del CSV de referencia (debe ser vacío)

### VERSION

- commit por fase: `feat(audit): <descripción>` (o `refactor(audit):` si la fase solo mueve
  código sin cambio funcional)
- CHANGELOG por módulo (`audit`, `bulk`, `dump`, `migrate`) con deprecaciones y su retirada prevista
- impacto en API pública (debe ser «ninguno» salvo adiciones opt-in)
- rollback por fase
- backlog de lo descartado o aplazado (con su `INV`/`H`)
- `## Directrices para Futuras IAs` del `TRACEABILITY.md` (punto canónico de auditoría, patrón de
  adaptadores, formato CSV congelado)

---

## Documentación (obligatoria al cerrar F5, parcial en cada fase que toque API)

- `docs/functional/audit.md` y `docs/api/audit.md` (arquetipos de `.github/DOCUMENTATION_STANDARD.md`),
  con diagrama Mermaid del flujo origen → adaptador → evento → sink
- actualizar `docs/functional/bulk_audit.md`, `docs/api/bulk_audit.md`, `docs/api/dump_reporter.md`
  y `docs/api/exceptions.md` para remitir al punto canónico
- entradas en `mkdocs.yml` (`nav:`) y `zensical build --strict` sin errores
- pie de figura de `docs/architecture.md` tras regenerar el diagrama de capas

## Sesión

Crea `.ai/sessions/<fecha>-audit-module/` desde `.ai/sessions/TEMPLATE/` (`00_REQUEST.md`,
`00_CONTEXT_SNAPSHOT.md`, `NN_<FASE>.md`, `TRACEABILITY.md`) y añade la fila en
`.ai/sessions/INDEX.md`.

---

## Invocación

```text
/new-feature

Aplica además .github/prompts/audit_module.prompt.md (manda sobre new_feature).
Objetivo: módulo de auditoría centralizado para bulk, dump y migrate
Módulo(s): src/util_bbdd/audit/ (nuevo); bulk/, dump/, migrate/ como consumidores
API esperada: sin cambios en la pública; nuevas capacidades opt-in
Contrato entrada: eventos de bulk, dump y migrate vía adaptadores
Contrato salida: CSV actual byte a byte idéntico + sinks opt-in
Reglas de negocio: cobertura de todo INV-* del inventario
Restricciones: sin dependencias nuevas; Regla #6; sin breaking changes
Motores/formatos: todos los de bulk/dump/migrate; CSV, Excel, JSON, HTML
Migraciones: no
Archivos relevantes: sí — .ai/audit/audit_module_baseline_inventory.md
Fases: PLAN y AUDIT_PLAN únicamente
```

En Copilot Chat: invoca **Plan Architect** con el mismo texto y este prompt adjunto.
