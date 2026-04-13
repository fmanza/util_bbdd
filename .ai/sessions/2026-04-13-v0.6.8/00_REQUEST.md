# REQUEST: v0.6.8-dev Initialization & Phase 4 Optimizations

**Date**: 13 de abril de 2026
**Repository**: fmanza/util_bbdd
**Branch**: develop
**Initiator**: Version Closer Agent
**Trigger**: v0.6.7 release closure

---

## Solicitud

Inicializar rama de desarrollo v0.6.8 y abordar hallazgos LOW de AUDIT_CODE_FASE2 del ciclo comparador (2026-04-13-comparar):

### Scope

**Phase 4 Optimizations** (identificadas en PLAN_FASE4.md):

1. **L1 (⭐⭐ Priority)**: MSSQL Bracket Regex Enhancement
   - Ruta: `src/util_bbdd/comparar/comparator.py:54`
   - Cambio: `r"\[(\w+)\]"` → `r"\[([^\]]+)\]"` para soportar espacios, guiones, etc. en SQL Server brackets
   - Ejemplo: `[My Column]`, `[My Table Name]`, etc.

2. **L2 (⭐ Priority)**: Performance Limitations Documentation
   - Ruta: `src/util_bbdd/comparar/comparator.py` (docstrings)
   - Agregar: nota sobre N+1 queries en schemas muy grandes
   - Contexto: cuando se comparan múltiples objetos en cascada

3. **L3 (⭐⭐ Priority)**: Exception Handling Tests
   - Ruta: `tests/comparar/test_comparator.py`
   - Agregar: 3 parametrized test cases para TimeoutError, PermissionError, Deadlock
   - Framework: pytest.mark.parametrize

---

## Restricciones

- No refactorizar módulos que no sean comparar/
- Cambios deben ser mínimos, focused en v0.6.8 (no anticipar v0.6.9)
- Tests deben pasar: `pytest tests/comparar/` + lint + mypy
- Documentación inline debe ser clara pero concisa

---

## Política de Ejecución

Seguir flujo estructurado:

```
PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
```

- Cada fase debe tener veredicto claro (GO/NO_GO)
- Si se descubren riesgos, escalarlos en AUDIT_PLAN
- Commits incrementales: L1 → L2 → L3 por separado

---

## Deliverables Esperados

1. **PLAN**: Detalle de cambios L1, L2, L3 con riesgos y beneficios
2. **AUDIT_PLAN**: Evaluación funcional/técnica/seguridad
3. **IMPLEMENT**: Cambios aplicados (L1 → L2 → L3)
4. **AUDIT_CODE**: Bugs potenciales, edge cases, type checking
5. **VERSION**: Commit messages + changelog entries
6. **SESSION_CLOSURE**: Resumen ejecutivo y artifacts

---

## Success Criteria

- [x] PLAN documento completo
- [ ] AUDIT_PLAN aprobado
- [ ] IMPLEMENT sin regresiones (tests aún passing)
- [ ] AUDIT_CODE sin hallazgos críticos
- [ ] VERSION listo para merge a develop
- [ ] Documentación actualizada
