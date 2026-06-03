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
| Estado actual de la librería | [Inicio](index.md) y [README](index.md) |
| Migrar código a versiones recientes (v0.6+) | [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) |
| Migración v0.5 → v0.6 | [MIGRATION_GUIDE_v0.6.7.md](MIGRATION_GUIDE_v0.6.7.md) |
| Detalle de un PR o decisión de diseño antigua | Historial de git (`git log`) y `CHANGELOG.md` |
| Resolver un error en código antiguo | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |

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
v0.8.0  (Actual: sistema de tipos + finalización)
```

Los detalles de cada hito están registrados en el
[`CHANGELOG.md`](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md).

## ⚠️ Notas Importantes

1. **No uses documentación histórica como referencia de código nuevo** — consulta siempre
   [Inicio](index.md) y el [README](index.md) para la API vigente (v0.8.0).
2. **Breaking changes** — si ves un error de import/API en código antiguo, revisa
   [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md).
3. **Reportes de issues** — indica tu versión de util_bbdd
   (`import util_bbdd; print(util_bbdd.__version__)`).
4. **Contribuciones** — lee [CONTRIBUTING.md](https://github.com/fmanza/util_bbdd/blob/main/.github/CONTRIBUTING.md).

## 🔗 Enlaces Útiles

- **Actual:** [Inicio](index.md) · [Referencia Técnica](api/intro.md)
- **Migración:** [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) · [MIGRATION_GUIDE_v0.6.7.md](MIGRATION_GUIDE_v0.6.7.md)
- **Histórico de cambios:** [CHANGELOG.md](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md)
- **Issues:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
