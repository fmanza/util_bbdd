# Petición — 2026-11-06 · Ola 11 de huecos de la web (G50, G51)

```text
/new-feature

Objetivo: ola 11 de docs/plan/UTIL_BBDD_GAPS_PLAN.md de util_bbdd_web (U-11.1 y U-11.2), un commit por fase
Detalle: util_bbdd_web/.ai/sessions/2026-11-06-gaps-g50-g51/PLAN.md y AUDIT_PLAN.md
Rutas: las de cada fase en el plan
Restricciones: solo opción y campo nuevos, compatibles; SemVer MINOR 5.4.0; manifest.json v1 se sigue leyendo
Condiciones: T3/T4 (zensical/Material con mermaid.min.js ausente) verificadas y documentadas; títulos de pages en texto plano (T5)
```

Inputs del prompt `new_feature` resueltos con el plan de la web (web 1.12.0 `39cf285`, plan `c6cb768`):

| Input | Valor |
|---|---|
| Objetivo | G50: referenciar un Mermaid publicado sin copiarlo. G51: índice de todas las páginas en `manifest.json` |
| Módulos | `doc/infrastructure/renderers/markdown/{_site,_writer,_site_pages,_text,markdown_generator}.py`, `doc/infrastructure/renderers/shared/print_config_manager.py`, `doc/application/use_cases/documentation_orchestrator.py`, `doc/database_documentation.py` (docstring) |
| API pública | `imprimir["markdown"]["mermaid_js_ref"]` (nueva, `str`); `manifest.json` `format_version` 2 con `pages` |
| Contrato de entrada | `mermaid_js_ref`: ruta relativa a `docs/` (POSIX) o URL `https://`; excluyente con `mermaid_js` |
| Contrato de salida | `mkdocs.yml` con `extra_javascript` = la referencia, nada copiado; `manifest.json` determinista (salvo `generated_at`) con `pages` |
| Reglas de negocio | No inventar metadatos; títulos en texto plano; determinismo; compatibilidad con v1 |
| Restricciones | Sin dependencias nuevas; prohibido refactorizar; MINOR 5.4.0 |
| Motores | Agnóstico (formato Markdown) |
| Migraciones | No |
| Archivos relevantes | Sí: sesión `2026-11-05-doc-markdown` (ADR-006, D1–D7) |
