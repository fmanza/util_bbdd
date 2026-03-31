---
applyTo: "tests/**"
---
# Tests

- Añade tests para toda nueva funcionalidad.
- Prefiere fixtures pequeñas y datos de esquema mínimos (tablas/relaciones pequeñas).
- Si hay generación de docs, usa snapshot testing o asserts sobre fragmentos clave.
- Evita depender de red; si necesitas BD, usa contenedor/local opcional o mocks.
- Para refactors, añade tests antes de cambiar código.
- Para hotfixes, añade tests que reproduzcan el bug antes de corregirlo.
- Usa pytest y sigue su convención de nombres (`test_*.py` y `def test_*`).
- Si el cambio afecta a la API pública, añade tests de integración que validen el comportamiento esperado.
- Para cambios de seguridad, añade tests que verifiquen la mitigación del riesgo.
- Mantén los tests rápidos y deterministas; evita pruebas que puedan fallar por factores externos.
