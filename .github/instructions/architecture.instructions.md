---
applyTo: "src/**/*.py"
---
# Arquitectura OO, SOLID y Patrones

> **TL;DR** — 3 capas (Foundation → Core Services → Domain Logic). Separar extracción, normalización, render y persistencia (SRP). Extender por adaptadores/Strategy, nunca editando flujos base estables (OCP). Las implementaciones deben respetar contratos comunes (LSP). Orquestar desde Protocol/ABC, no desde clases concretas (DIP).

## Objetivo
Definir reglas de arquitectura para una librería multibase orientada a introspección, comparativas de esquemas y generación de documentación.

## Principios de diseño
- Claridad antes que abstracción: cada capa y cada clase deben tener un límite explícito.
- Evolución incremental: aplicar patrones solo cuando reducen acoplamiento o duplicación real.
- Compatibilidad: preservar API pública y contratos existentes salvo decisión explícita.

## Checklist SOLID para PR
- `SRP`: la clase/módulo tiene una razón de cambio dominante.
- `OCP`: agregar un motor/formato no requiere editar múltiples módulos estables.
- `LSP`: implementaciones concretas son intercambiables bajo el mismo contrato.
- `ISP`: contratos pequeños y orientados al uso; sin métodos no relevantes.
- `DIP`: capas de orquestación dependen de interfaces (`Protocol`/`ABC`), no de concretos.

## Patrones recomendados y uso
- `Strategy`: variaciones por motor o formato de salida.
- `Factory Method` / `Abstract Factory`: creación de adaptadores, conexiones y servicios por motor.
- `Adapter`: unificar diferencias entre drivers o APIs externas.
- `Template Method`: pipeline común con hooks por implementación.
- `Facade`: API de alto nivel para orquestar introspección, comparativa y render.
- `Builder`: construcción incremental de artefactos documentales.
- `Query Object` (Fowler): representar consultas de metadatos y aislar SQL.
- `Repository` (Fowler): acceso de lectura/escritura desacoplado de la capa de dominio.
- `Data Mapper` (Fowler): mapear filas/tablas a modelos de metadatos.
- `Identity Map` (Fowler): evitar cargas duplicadas dentro de una unidad de trabajo.

## Anti-patrones
- `God class`.
- Condicionales por motor repartidos por toda la base de código.
- Mezclar lógica de negocio con detalles de render o transporte.
- Patrones aplicados por inercia sin necesidad demostrable.

## Evidencia mínima en cambios arquitectónicos
- Justificación del patrón elegido y alternativa descartada.
- Contrato tipado (`Protocol`/`ABC`) y al menos una implementación.
- Tests de contrato (incluye sustitución de implementaciones).
- Riesgos de compatibilidad y estrategia de rollback documentados.

## Referencias
- `G:\Mi unidad\Trabajo\Manuales\Desarrollo\Patrones de Diseño\design-patterns-es.pdf`
- https://martinfowler.com/eaaCatalog/
