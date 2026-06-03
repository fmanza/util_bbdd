# Documentación de Versiones Históricas

Este archivo documenta dónde encontrar la documentación histórica de util_bbdd para distintas versiones y períodos de desarrollo.

## 📚 Índice de Versiones

### Releases Principales (Vigentes)
- **v0.8.0** (Actual) — [CHANGELOG.md](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md) — Última versión, cambios respecto a v0.7.0
- **v0.7.x / v0.6.x** (Históricas) — [archive/](https://github.com/fmanza/util_bbdd/tree/main/docs/archive/) — Documentación archivada de versiones anteriores

### Fases de Refactorización Históricas
- **v0.1 → v0.3.0** (PR 0-8) — [archive/releases/v0.1-v0.3.0/](https://github.com/fmanza/util_bbdd/tree/main/docs/archive/releases/v0.1-v0.3.0/) — Refactorización inicial completa con checklists de cada PR

### Versiones Archivadas por Período
- **v0.5.6** — [archive/versions/v0.5.6/](https://github.com/fmanza/util_bbdd/tree/main/docs/archive/versions/v0.5.6/) — Documentación técnica específica (procedures, refactors de Jinja2, etc.)

## 🔍 Guía Rápida: ¿Dónde Buscar?

### "¿Cómo migrar mi código de la versión X a Y?"
👉 Usa [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) para versiones recientes (v0.6+)
👉 Para migración v0.5 → v0.6, consulta [MIGRATION_GUIDE_v0.6.7.md](MIGRATION_GUIDE_v0.6.7.md)

### "¿Qué cambió en PR X?"
👉 Consulta [archive/releases/v0.1-v0.3.0/](https://github.com/fmanza/util_bbdd/tree/main/docs/archive/releases/v0.1-v0.3.0/) para PRs 0-8
👉 Para versiones más recientes, revisa [CHANGELOG.md](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md)

### "¿Cuál es el estado actual de util_bbdd?"
👉 Lee [README.md](index.md) y [Inicio](index.md) (documentación vigente)
👉 Para detalles técnicos, consulta [API_REFERENCE.md](api/intro.md)

### "¿Necesito info histórica de v0.5.6?"
👉 Verifica [archive/versions/v0.5.6/](https://github.com/fmanza/util_bbdd/tree/main/docs/archive/versions/v0.5.6/)
👉 Nota: Esta es documentación de referencia; código actual es v0.8.0+

## 📊 Timeline de Versiones

```
v0.0.5 (Initial Setup)
    ↓
v0.1.0-v0.3.0 (PR 0-8 Refactorization) ← [archive/releases/v0.1-v0.3.0/]
    ↓
v0.4.0 (Early stable)
    ↓
v0.5.0-v0.5.6 (Feature additions) ← [archive/versions/v0.5.6/]
    ↓
v0.6.0-v0.7.0 (Mature stable)
    ↓
v0.8.0 (Current, type system + finalization) ← CHANGELOG.md
```

## 🎯 Propósito de Cada Sección

### `/archive/releases/`
- **Contenido:** Documentación de refactorización por fase (PR 0-8)
- **Audiencia:** Desarrolladores que desean entender evolución histórica
- **Relevancia:** Histórica (decisiones de diseño pasadas, breaking changes integrados)

### `/archive/versions/`
- **Contenido:** Documentación técnica específica de versiones (v0.5.6+)
- **Audiencia:** Usuarios manteniendo versiones antiguas
- **Relevancia:** Referencia (procedimientos, configuraciones de ese período)

### Raíz (`docs/`)
- **Contenido:** Documentación vigente (versión actual: v0.8.0)
- **Audiencia:** Usuarios nuevos y actuales
- **Relevancia:** **VIVA** (actualizada regularmente)

## ⚠️ Notas Importantes

1. **No uses docs históricos para nuevo código** — Siempre consulta [README.md](index.md) y [Inicio](index.md) para referencias actuales

2. **Breaking changes** — Si ves error de import/API en código antiguo, revisa [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

3. **Reportes de issues** — Si reportas un bug, menciona tu versión de util_bbdd (`import util_bbdd; print(util_bbdd.__version__)`)

4. **Contribuciones** — Lee [CONTRIBUTING.md](https://github.com/fmanza/util_bbdd/blob/main/.github/CONTRIBUTING.md) para guía actual

## 📝 Estructura Completa del Archivo

```
docs/
├── README.md (versión actual, v0.8.0)
├── CHANGELOG.md (histórico de versiones)
├── MIGRATION_GUIDE.md (guía de migración vigente)
├── MIGRATION_GUIDE_v0.6.7.md (específica para v0.6.7)
├── legacy-versions.md ← Este archivo
├── archive/
│   ├── releases/
│   │   └── v0.1-v0.3.0/ (PRs 0-8 refactorization)
│   │       ├── README.md (overview de PR 0-8)
│   │       ├── 00_ESTADO_COMPLETO_PR0.md
│   │       ├── 01_ESTADO_COMPLETO_PR1.md
│   │       ... (PR 2-8)
│   │       └── RESUMEN_CONSOLIDADO_PRs_5_a_8.md
│   ├── versions/
│   │   └── v0.5.6/ (documentación específica de v0.5.6)
│   │       ├── jinja2_refactor.md
│   │       ├── procedures_funciones.md
│   │       └── ... (otros docs de v0.5.6)
│   └── plan-legacy/ (archivos adicionales históricos)
├── examples/ (ejemplos actuales)
└── api/ (referencia API actual)
```

## 🔗 Enlaces Útiles

- **Actual:** [README.md](index.md) | [API_REFERENCE.md](api/intro.md)
- **Migración:** [MIGRATION_GUIDE_v0.6.7.md](MIGRATION_GUIDE_v0.6.7.md) | [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **Histórico:** [https://github.com/fmanza/util_bbdd/tree/main/docs/https://github.com/fmanza/util_bbdd/tree/main/docs/archive/releases/v0.1-v0.3.0/README.md](https://github.com/fmanza/util_bbdd/tree/main/docs/https://github.com/fmanza/util_bbdd/tree/main/docs/archive/releases/v0.1-v0.3.0/README.md)
- **Versiones:** [https://github.com/fmanza/util_bbdd/tree/main/docs/https://github.com/fmanza/util_bbdd/tree/main/docs/archive/versions/v0.5.6/](https://github.com/fmanza/util_bbdd/tree/main/docs/https://github.com/fmanza/util_bbdd/tree/main/docs/archive/versions/v0.5.6/)
- **Issues:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
