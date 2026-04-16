# REQUEST

## Objetivo
Refactorizar `src\util_bbdd\comparar` para quitar excepciones genéricas (`ValueError`, `Exception`, `NotImplementedError`) y crear excepciones específicas para cada tipo de error que pueda ocurrir durante la comparación.

## Request Saneado
Refactorizar módulo de comparación de esquemas para:
1. Crear jerarquía de excepciones específicas derivadas de `DatabaseException`
2. Reemplazar `ValueError`, `Exception` genéricas en validators y reporters
3. Mejorar manejo de errores en generación de reportes
4. Mantener comportamiento funcional sin cambios en lógica de comparación

## Restricciones
- **Alcance**: Solo la generación de documentación, sin cambios en la lógica del módulo comparar
- **Política de compatibilidad**: Se autoriza romper contratos públicos
- **Arquitectura**: Leer `.ai/architecture.md` y `CLAUDE.md` antes de proponer cambios
- **Documentación**: Seguir `.ai/sessions/INDEX.md` y `.ai/sessions/TEMPLATE/TRACEABILITY.md`

## Entrada del Usuario
```
Refactorizar src\util_bbdd\comparar para quitar la exceciones genéricas y crear excepciones específicas para cada tipo de error que pueda ocurrir durante la comparación, como por ejemplo: ComparacionException, ConexionException, ValidacionException, etc.
[...]
Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.
```

## Definición de Done
- [ ] 4 nuevas excepciones creadas en `_core/exceptions.py`
- [ ] Jerarquía: `ComparerError` base + 3 subclases específicas
- [ ] 6 `pytest.raises(ValueError)` actualizados a nuevas excepciones
- [ ] Todos los tests pasan (1878 passed)
- [ ] Lint limpio
- [ ] Type-check limpio (ignoring pre-existing errors)
- [ ] `TRACEABILITY.md` documentado

## Autorización
Usuario autoriza romper contratos públicos: **SÍ** ("Si" respondió a AUDIT_PLAN)
