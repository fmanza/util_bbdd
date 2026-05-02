# Prompt: technical_doc — Documentación técnica con Mermaid

Genera o actualiza diagramas Mermaid.js y documentación técnica para módulos de **util_bbdd**,
basándote solo en código, configuración y documentación existente verificable.

## Instrucción al modelo

```
Actúa como arquitecto de software senior especializado en Python, documentación técnica y mantenibilidad.

Analiza el módulo [NOMBRE_MÓDULO] de util_bbdd y la documentación existente relacionada.
No asumas dependencias, motores, APIs ni capacidades que no aparezcan en el código real,
`pyproject.toml`, README, `docs/` o `mkdocs.yml`.

Genera documentación técnica en Markdown con estas secciones:

## Responsabilidad del módulo
Una frase. Qué hace exactamente este módulo en el sistema.

## Diagrama
Elige el tipo de diagrama más apropiado:
- `sequenceDiagram` → si el módulo procesa requests/responses o tiene flujo I/O
- `flowchart TD` → si el módulo tiene lógica de decisión o pipeline de transformación
- `classDiagram` → si el módulo expone jerarquía de clases relevante para el consumidor

Criterios del diagrama:
- Omite: credenciales, puertos, variables internas, rutas de ficheros de implementación
- Incluye: actores externos, operaciones de negocio, flujo de datos, puntos de decisión
- Máximo 12 nodos para legibilidad sin zoom
- Usa etiquetas en español para actores y acciones
- Si no hay suficiente información para un diagrama correcto, declara la limitación y no inventes flujo

## API pública
Tabla con columnas: | Función/Clase | Firma simplificada | Descripción | Retorna |
Solo las funciones/clases exportadas en __all__ o __init__.py.

## Contrato de entrada
Parámetros de las funciones principales con tipos y restricciones.
Formato: tabla con columnas: | Parámetro | Tipo | Descripción | Restricciones |

## Contrato de salida
Qué retorna cada función principal. Tipos, estructura de datos, casos especiales.

## Errores y casos especiales
Qué ocurre con entradas inválidas, valores fuera de rango, o conexión fallida.

## Ejemplo técnico mínimo
Incluye un ejemplo de uso verificable de la API pública cuando sea posible.
Debe usar datos ficticios seguros y no requerir credenciales reales.

---

Restricciones:
- SOLO incluye lo exportado públicamente, no implementación interna
- El diagrama debe ser Mermaid válido en bloque fenced `mermaid`
- No inventes firmas, excepciones, tipos, dependencias ni efectos secundarios
- Si falta información, añade "Pendiente de verificación" con puntos concretos
- Responde SOLO con el Markdown
```

## Cómo usar este prompt

### Modo módulo único — Claude Code

```
Lee [ruta_del_módulo] y genera documentación técnica con diagrama Mermaid
usando el prompt en .github/prompts/technical_doc.prompt.md.
Guarda el resultado en docs/[sección_apropiada]/[nombre_módulo].md.
Actualiza mkdocs.yml si se crea o mueve una página.
No inventes firmas ni efectos secundarios; marca como pendiente lo no verificable.
```

### Modo módulo único — Copilot Chat

```
#file:.github/prompts/technical_doc.prompt.md
#file:[ruta_del_módulo]

Genera la documentación técnica con diagrama Mermaid del módulo indicado.
```

### Modo proyecto completo (iterativo por módulo)

No uses un único prompt masivo. Recorre el proyecto en fases:

```
Fase 1 — Inventariar módulos públicos desde src/util_bbdd/.
  Lista funciones/clases exportadas en __init__.py o __all__; agrúpalas por área funcional.

Fase 2 — Para cada módulo (o área), aplica technical_doc.prompt.md:
  "Lee [ruta] y genera docs/api/[nombre].md con responsabilidad, diagrama Mermaid,
   API pública, contratos de entrada/salida, errores y ejemplo técnico mínimo.
   Elige el tipo de diagrama según el patrón del módulo (ver tabla más abajo).
   Marca como pendiente lo no verificable."

Fase 3 — Actualizar mkdocs.yml:
  Añade o actualiza entradas en la sección docs/api/ del nav.

Fase 4 — Revisión cruzada:
  Contrasta con docs/functional/ y docs/examples/ para detectar inconsistencias de contratos.
```

## Tipos de diagrama recomendados

| Patrón real del módulo | Diagrama recomendado | Motivo |
|---|---|---|
| Flujo entre usuario, CLI, servicio externo y salida | `sequenceDiagram` | Muestra interacción y orden temporal |
| Pipeline de transformación o decisiones | `flowchart TD` | Muestra ramas, validaciones y resultado |
| Jerarquía pública de clases | `classDiagram` | Muestra contratos orientados a objetos |

## Prompt dedicado para infografías Mermaid

Usa este prompt cuando necesites solo el diagrama, sin la documentación técnica completa:

```
Basándote únicamente en la lógica verificable del módulo [Nombre], genera exclusivamente
el código Mermaid.js para un diagrama de secuencia que ilustre la interacción entre el
usuario, el componente principal y sus salidas.
Omite: credenciales, puertos, variables internas, rutas de implementación, nombres de bases de datos.
Incluye: actores externos, operaciones de negocio, puntos de decisión, flujo de datos.
Máximo 12 nodos. Etiquetas en español.
Si el flujo no puede inferirse con seguridad, declara qué información falta en lugar de inventar.
```

## Exclusiones actuales

- No incluir ejemplos de generación mediante APIs externas por el momento.
- No usar un único prompt masivo para todo el proyecto; iterar módulo a módulo o por área.

## Output esperado

Markdown con las 6 secciones, incluyendo un bloque mermaid válido que se renderiza
correctamente en MkDocs Material y en GitHub, más un ejemplo técnico mínimo cuando sea verificable.
