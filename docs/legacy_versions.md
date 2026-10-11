# Documentación de Versiones Históricas

Este archivo explica dónde encontrar información sobre versiones anteriores de util_bbdd.

!!! note "Documentación histórica retirada"
    La documentación de trabajo por versión (notas de release internas, planes de
    refactorización por PR, informes de fase, etc.) **ya no forma parte de la documentación
    publicada**. Era material de proceso, no documentación de uso. El histórico de cambios
    vigente y consultable es el [`CHANGELOG.md`](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md)
    y el propio historial de commits del repositorio.

## 📚 Dónde buscar información histórica

| Necesitas… | Consulta |
|---|---|
| Cambios entre versiones | [`CHANGELOG.md`](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md) |
| Estado actual de la librería | [Inicio](index.md) y [README](https://github.com/fmanza/util_bbdd/blob/main/README.md) |
| Migrar código de 0.x a 1.0 | [guides/api_1_0_migration.md](guides/api_1_0_migration.md) |
| Migrar código anterior a v0.6.3 | [guides/migration_guide.md](guides/migration_guide.md) |
| Migración v0.6.6 → v0.6.7 | [guides/migration_guide_v0.6.7.md](guides/migration_guide_v0.6.7.md) |
| Detalle de un PR o decisión de diseño antigua | Historial de git (`git log`) y `CHANGELOG.md` |
| Resolver un error en código antiguo | [guides/troubleshooting.md](guides/troubleshooting.md) |

## 📊 Timeline de Versiones

```
v0.0.5  (Initial Setup)
   ↓
v0.1.0 – v0.3.0  (Refactorización inicial, PR 0-8)
   ↓
v0.4.0  (Primera estable)
   ↓
v0.5.0 – v0.5.6  (Adición de funcionalidades)
   ↓
v0.6.0 – v0.7.0  (Madurez / estable)
   ↓
v0.8.0 – v0.10.0  (Sistema de tipos + rendimiento de bulk/dump)
   ↓
v0.11.0 – v0.42.x  (Auditoría común en v0.29, metadatos centralizados por lotes en v0.31 — ver CHANGELOG)
   ↓
v0.43.0 – v0.44.0  (Superficie pública 1.0 con alias obsoletos)
   ↓
v1.0.0  (API pública estable bajo SemVer)
   ↓
v1.1.0  (Actual)
```

La vista panorámica de versiones está en el [Roadmap](roadmap.md); los detalles de cada hito,
en el [`CHANGELOG.md`](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md).

## ⚠️ Notas Importantes

1. **No uses documentación histórica como referencia de código nuevo** — consulta siempre
   [Inicio](index.md) para la API vigente (1.x).
2. **Breaking changes** — si ves un error de import/API en código antiguo, revisa primero
   [Migración a la API 1.0](guides/api_1_0_migration.md) y, para código anterior a v0.6.3,
   [guides/migration_guide.md](guides/migration_guide.md).
3. **Reportes de issues** — indica tu versión de util_bbdd
   (`python -c "from importlib.metadata import version; print(version('util_bbdd'))"`).
4. **Contribuciones** — lee [CONTRIBUTING.md](https://github.com/fmanza/util_bbdd/blob/main/.github/CONTRIBUTING.md).

## 🔗 Enlaces Útiles

- **Actual:** [Inicio](index.md) · [Referencia Técnica](api/intro.md)
- **Migración:** [guides/api_1_0_migration.md](guides/api_1_0_migration.md) · [guides/migration_guide.md](guides/migration_guide.md) · [guides/migration_guide_v0.6.7.md](guides/migration_guide_v0.6.7.md)
- **Histórico de cambios:** [CHANGELOG.md](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md)
- **Issues:** [guides/troubleshooting.md](guides/troubleshooting.md)
