# 00_REQUEST — 2026-09-27d-export-safety

## Solicitud (en orden)

1. «Revisa en src\dump, no se crea el fichero Excel, solo el CSV».
2. «Los LOG están en C:\Desarrollo\Proyectos\pruebas_util\ficheros\salida\log, revisa los de hoy».
3. `/audit-code` — «revises todo lo relacionado con exportación y una solución definitiva».
4. Variante (a) para no perder el resultado del volcado: `DumpReportError.result`.
5. Commits; PLAN y AUDIT_PLAN de lo pendiente; `/audit-code` de los commits.
6. IMPLEMENT de lo pendiente, opción (a) para el diagrama de capas (aceptar el import de módulo `bulk → connection`).
7. Commits; `/version-closure`.

## Restricciones

- Sin tocar los ficheros del usuario fuera del repo (`pruebas_util`): solo lectura; las pruebas sobre su CSV, con copias
  en el scratchpad.
- Sin romper `except OSError` ni la jerarquía pública de excepciones.
- `_core` no puede importar de `dump` (Regla #6, capas de `docs/architecture.md`).
