# 🔧 Guía: Pasos para Implementar una Refactorización en util_bbdd

## 📋 Metodología

Basado en **Metodología IA para VS Code + GitHub**, adaptado a este proyecto Python.

---

## ✅ Pre-refactoring: Preparation

### 1. **Define el Objetivo** (sin código aún)
- ¿Qué problema resuelve? (duración, mantenibilidad, performance, seguridad)
- ¿Qué módulos afecta?
- ¿Hay breaking changes?
- ¿Impacto en retrocompatibilidad?

**Entregable:** Documento en `.ai/sessions/<fecha>/00_REQUEST.md`

```markdown
## Objetivo
[Descripción clara del problema]

## Scope
- Archivos afectados: [lista]
- Breaking Change: Sí/No
- Retrocompatibilidad esperada: [especificar]

## Justificación
[Por qué es importante ahora]
```

---

## 📐 PHASE 1: PLAN

### 2. **Crear Sesión**
```bash
mkdir -p .ai/sessions/$(date +%Y-%m-%d-%H%M%S)-refactor-<nombre-corto>
cd .ai/sessions/<sesion>/
```

### 3. **Snapshot del Contexto Actual**
Copia en `.ai/sessions/<sesion>/00_CONTEXT_SNAPSHOT.md`:
```markdown
## Estado Actual

### Archivos Afectados
- [lista de archivos existentes]

### Dependencias Críticas
- [módulos internos]
- [librerías externas]

### Testing Baseline
- Coverage actual: [%]
- Pruebas criticas: [nombres]

### Versión Actual
- Version: [x.y.z]
- Branch: [develop]
```

### 4. **Ejecutar PLAN**

Lanza el prompt `.github/prompts/refactor.prompt.md` con contexto:

**Input esperado:**
- `.ai/sessions/<sesion>/00_REQUEST.md`
- `.ai/sessions/<sesion>/00_CONTEXT_SNAPSHOT.md`

**Output esperado en `.ai/sessions/<sesion>/00_PLAN.md`:**
```markdown
## PLAN: [Título]

### Objetivo
[Reiteración clara]

### Rutas/Archivos Afectados
- `src/util_bbdd/module1.py`: [qué cambia]
- `src/util_bbdd/module2.py`: [qué cambia]

### Componentes Implicados
- [Clases, funciones principales]

### Tipos Necesarios
- [Nuevos tipos, cambios en _core/types.py]

### Estrategia de Deprecación
- [Si hay breaking changes]

### Riesgos Identificados
- Funcionales: [lista]
- Técnicos: [lista]
- Seguridad: [lista]

### Impacto en Tests
- Tests a actualizar: [lista]
- Nuevos tests necesarios: [lista]
```

---

## 🔍 PHASE 2: AUDIT_PLAN

### 5. **Revisar Riesgos**

Ejecuta `.github/prompts/audit_code.prompt.md` con el PLAN como input.

**Output esperado en `.ai/sessions/<sesion>/01_AUDIT_PLAN.md`:**
```markdown
## AUDIT_PLAN

### ✅ Aspecto Funcional
- [Verificar edge cases]
- [Verificar retrocompatibilidad]
- [Impacto en usuarios legacy]

### 🛡️ Aspecto Técnico
- [Ciclos de importación]
- [Coupling/cohesion]
- [Performance implications]

### 🔒 Aspecto Seguridad
- [SQL injection prevention]
- [Credential handling]
- [Audit trail updates]

### 🎯 Simplificaciones Posibles
- [Reducciones en scope]
- [Oportunidades de tech debt cleanup]

## VEREDICTO
- **GO** | **NO_GO** | **GO_CONDICIONAL**
- Condiciones (si aplica): [lista]
```

### 6. **GO/NO_GO Decision**

- Si **NO_GO**: Replanificar o cancelar
- Si **GO_CONDICIONAL**: Documentar condiciones a cumplir
- Si **GO**: Proceder a IMPLEMENT

---

## 🚀 PHASE 3: IMPLEMENT

### 7. **Preparar Branch**
```bash
git checkout develop
git pull origin develop
git checkout -b refactor/<nombre-corto>
```

### 8. **Ejecutar Cambios**

Siguiendo el PLAN, implementar:

**Por cada archivo/módulo:**
- Actualizar `src/util_bbdd/<modulo>.py`
- Mantener wrappers legacy solo si siguen siendo una decisión explícita del alcance
- Agregar type hints
- Actualizar docstrings

**Después de cada cambio:**
```bash
# Type check
mypy src/util_bbdd --strict

# Lint
ruff check src/util_bbdd

# Tests (quick feedback)
pytest tests/ -k "<test_pattern>" -v
```

### 9. **Update Tests**

En `tests/`:
- Actualizar tests existentes que fallen
- Agregar nuevos tests (coverage ≥90%)
- Verificar fixtures en `conftest.py`

```bash
pytest --cov=src/util_bbdd --cov-report=term-missing
```

### 10. **Documentación**

Actualizar:
- `.ai/architecture.md` (si hay cambios estructurales)
- `README.md` (si API pública cambia)
- Docstrings (Google-style)

**Guardar progreso en `.ai/sessions/<sesion>/03_IMPLEMENT.md`:**
```markdown
## IMPLEMENT: [Titulo]

### Cambios por Archivo
- `src/util_bbdd/x.py`: [qué se cambió]
- `tests/test_x.py`: [qué tests se agregaron]

### Testing Report
- Tests agregados: [N]
- Coverage: [%]
- Todos pasan: Sí/No

### Diferencias vs PLAN
- [Si hay desviaciones, justificar]
```

---

## 🔎 PHASE 4: AUDIT_CODE

### 11. **Code Review Checklist**

Ejecuta `.github/prompts/audit_code.prompt.md`:

**Validar:**
```markdown
## AUDIT_CODE

### ✅ Bugs Potenciales
- [None | lista de hallazgos]

### ✅ Edge Cases
- [None | lista de escenarios no cubiertos]

### ✅ Performance
- [Regressions check]
- [Optimizations check]

### ✅ Seguridad
- [SQL injection prevention]
- [Credentials handling]

### ✅ Type Safety
- [mypy --strict: PASS/FAIL]

### ✅ Test Coverage
- [Coverage ≥90%: PASS/FAIL]
- [All tests pass: PASS/FAIL]

### ✅ Deuda Técnica
- [None introduced: Sí/No]

## VEREDICTO
- **ACCEPT** | **REJECT** | **ACCEPT_WITH_NOTES**
```

### 12. **Fix Issues**

Si hay hallazgos:
- Actualizar código
- Re-run checks
- Iter hasta ACCEPT

---

## 📦 PHASE 5: VERSION & CLOSURE

### 13. **Update Versioning**

En `pyproject.toml`:
```toml
version = "0.x.y"  # Increment según changes
```

### 14. **Changelog Entry**

En `CHANGELOG.md`:
```markdown
## [0.x.y] - YYYY-MM-DD

### Changed
- [descripción de cambios]

### Fixed
- [si aplica]

### Deprecated
- [si aplica, con removal timeline]
```

### 15. **Commit & PR**

```bash
git add -A
git commit -m "refactor(<scope>): <description>

- <detail 1>
- <detail 2>

Closes #<issue_number>
"

git push origin refactor/<nombre>
# Crear PR develop → main o según la política vigente del repo
```

### 16. **Final Report**

En `.ai/sessions/<sesion>/07_VERSION_MANAGEMENT.md`:
```markdown
## VERSION_MANAGEMENT

### Commit
- Hash: [git hash]
- Message: [commit message]

### Changelog
- Version: 0.x.y
- Entries: [N]

### Breaking Changes
- None | [lista con mitigación]

### Rollback Strategy
- git revert <commit>

### Pruebas Sugeridas
- [Tests manuales si aplica]
- [Integration tests]
```

---

## 📊 PHASE 6: TRACEABILITY

### 17. **Log Completo**

Crear `.ai/sessions/<sesion>/TRACEABILITY.md`:
```markdown
## TRACEABILITY

| Fase          | Entrada                    | Salida                     | Estado   | Notas                 |
|---------------|---------------------------|--------------------------|----------|----------------------|
| REQUEST       | User request              | 00_REQUEST.md             | ✅      | [si aplica]          |
| CONTEXT       | Repository state          | 00_CONTEXT_SNAPSHOT.md    | ✅      |                      |
| PLAN          | CONTEXT + copilot prompt  | 00_PLAN.md                | ✅      |                      |
| AUDIT_PLAN    | PLAN + audit prompt       | 01_AUDIT_PLAN.md + GO/NO  | ✅      | GO_CONDICIONAL       |
| IMPLEMENT     | PLAN + code changes       | 03_IMPLEMENT.md + branch  | ✅      |                      |
| AUDIT_CODE    | code + audit prompt       | 04_AUDIT_CODE.md + review | ✅      | ACCEPT_WITH_NOTES    |
| VERSION       | code + docs               | 07_VERSION_MANAGEMENT.md  | ✅      |                      |
| CLOSURE       | All phases complete       | PR merged                 | ⏳      | Pending merge        |

### Key Decisions
- [Decisión 1: razón]
- [Decisión 2: razón]

### Lessons Learned
- [Lo que funcionó bien]
- [Lo que se puede mejorar]
```

---

## ⚡ Quick Reference Checklist

```
✅ PRE-REFACTOR
  [ ] Objetivo definido
  [ ] Sesión creada (.ai/sessions/<fecha>/)
  [ ] 00_REQUEST.md y 00_CONTEXT_SNAPSHOT.md

✅ PLAN PHASE
  [ ] 00_PLAN.md ejecutado y documentado
  [ ] 01_AUDIT_PLAN.md revisado
  [ ] Veredicto: GO (proceder)

✅ IMPLEMENT PHASE
  [ ] Branch creada (refactor/<nombre>)
  [ ] Cambios código completados
  [ ] Tests actualizados y pasan (coverage ≥90%)
  [ ] 03_IMPLEMENT.md documentado

✅ AUDIT PHASE
  [ ] 04_AUDIT_CODE.md ejecutado
  [ ] Hallazgos resueltos
  [ ] Veredicto: ACCEPT

✅ VERSION PHASE
  [ ] pyproject.toml versión actualizada
  [ ] CHANGELOG.md entry
  [ ] 07_VERSION_MANAGEMENT.md documentado
  [ ] Commit + push

✅ CLOSURE
  [ ] PR creada
  [ ] TRACEABILITY.md completado
  [ ] Sesión cerrada
```

---

## 🔗 Referencia de Archivos

- **Prompts:** `.github/prompts/<type>.prompt.md`
- **Contexto:** `.ai/context/<document>.md`
- **Sesión actual:** `.ai/sessions/<sesion>/<archivo>.md`
- **Código:** `src/util_bbdd/`
- **Tests:** `tests/`
- **Build config:** `pyproject.toml`, `pytest.ini`

---

## 💡 Notas Finales

1. **Una intención por sesión**: No mezcles feature, hotfix y refactor
2. **Evidencia por cada fase**: Guardar outputs
3. **Go/No-Go explícito**: Antes de IMPLEMENT
4. **Coverage ≥90%**: Non-negotiable
5. **Retrocompatibilidad**: No asumirla por defecto; documenta explícitamente cuándo se conserva y cuándo se rompe
6. **Rollback ready**: Siempre tener estrategia de rollback

¡Listo para refactorizar! 🚀
