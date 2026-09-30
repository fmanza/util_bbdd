<!-- arquetipo: informativo-libre -->
# Roadmap de util_bbdd

Visión de versiones de la librería: qué se ha entregado, qué hay en curso y hacia dónde va.
El detalle exhaustivo de cada cambio vive en el
[CHANGELOG](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md) (formato
[Keep a Changelog](https://keepachangelog.com/) + [SemVer](https://semver.org/)); esta página
es la vista panorámica.

> **Versión vigente: v0.21.0.** Las series `0.x` siguen siendo pre-estables: la API se mantiene
> mayormente compatible, pero puede haber cambios acotados entre minors. La estabilización formal
> llega con `v1.0.0`. Las versiones posteriores a `v0.10.0` aún no están en la tabla de abajo: su
> detalle está en el CHANGELOG.

## En curso (`develop` / Unreleased)

- **bulk** — Guía de tuning de `commit_every_n_chunks` para cargas masivas en MariaDB/MySQL
  (evita la degradación exponencial del undo log). _En documentación._

Ver la sección `[Unreleased]` del
[CHANGELOG](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md) para el estado al día.

## Entregado

### Serie 0.7 – 0.10 — Rendimiento y cobertura de tipos

| Versión | Fecha | Hito |
|---|---|---|
| `v0.10.0` | 2026-06-01 | Vías rápidas de INSERT por motor en `bulk` (PostgreSQL `COPY` vía psycopg3, MySQL/MariaDB multi-fila); `dump` reutiliza la resolución única por tabla; fix de la vía rápida de PostgreSQL que era código muerto con psycopg3. |
| `v0.9.0` | 2026-06-01 | Palancas de rendimiento opt-in en `dump` (cadencia de commit, gestión de índices, paralelización), todas desactivadas por defecto y combinables. |
| `v0.8.0` | 2026-04-21 | **Cobertura completa del sistema de tipos** (introspección de tipos avanzados en los 8 motores: composite/OBJECT/UDT, JSON schema, ARRAY); hotfix de finalización del pool en cierre del intérprete. Ver [plan original (entregado)](v0.8.0/PLAN_v0.8.0_TYPE_SYSTEM_IMPROVEMENTS.md). |
| `v0.7.0` | 2026-04-21 | Monitorización de rendimiento: timing automático de operaciones en bulk CRUD (columna `tiempo_seg` en la auditoría CSV); retirada de scripts legacy con credenciales hardcodeadas. |

### Serie 0.1 – 0.6 — Construcción y consolidación

| Versión | Hito |
|---|---|
| `v0.6.7` | Comparador de esquemas, imports canónicos desde la raíz, estructura actual como estándar. |
| `v0.6.0 – v0.6.6` | Grafos multinivel, HTML tabulado, contrato documental, capa de agentes Copilot, estabilización de managers y testing. |
| `v0.5.0` | Refactorización arquitectónica (jerarquía de 3 niveles). |
| `v0.4.0` | Consolidación de conexiones (primera estable). |
| `v0.3.0` | Soporte PostgreSQL mejorado. |
| `v0.2.0` | Documentación de BD automática mejorada. |
| `v0.1.0` | CRUD base + auditoría. |

## Futuro

- **`v1.0.0`** — API estable bajo SemVer estricto y cobertura de tests ≥ 85%.

Ideas exploradas pero **fuera de alcance** por ahora (registradas en el
[plan de tipos v0.8.0](v0.8.0/PLAN_v0.8.0_TYPE_SYSTEM_IMPROVEMENTS.md)):
validación completa de JSON Schema, generación de dataclasses/TypeScript, motores no relacionales
(MongoDB, Cassandra) y notificaciones de cambio de esquema en tiempo real.

---

*Esta página es planificación (`informativo-libre`): orientativa y sujeta a cambios. La fuente de
verdad de lo ya publicado es el
[CHANGELOG](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md).*
