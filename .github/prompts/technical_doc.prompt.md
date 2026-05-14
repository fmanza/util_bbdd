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


## Arquitectura física (solo si aplica)
Añade esta sección INMEDIATAMENTE DESPUÉS del diagrama principal si el módulo o proyecto
contiene cualquiera de los siguientes indicadores:
- Web API: FastAPI, Flask, Django, APIRouter, directorio src/**/web/
- Servidor web / proxy: uvicorn, gunicorn, nginx, Caddy, traefik
- Base de datos: SQLAlchemy, psycopg2, pymongo, redis, sqlite3, alembic
- Contenedores: Dockerfile, docker-compose.yml, .dockerignore

La sección contiene:
1. Un párrafo con los componentes de infraestructura detectados (no inventes).
2. Un diagrama architecture-beta para representar la topología física de servicios.

Usa group para agrupar servicios en el mismo contenedor o red.
Etiquetas en español. Solo incluye lo que está en el código real.

Restricciones críticas de sintaxis architecture-beta:
- Labels []: solo alfanuméricos y espacios. NUNCA uses +, #, &, (, ) u otros símbolos.
- IDs de servicio distintos del icono: service webserver(server), NUNCA service server(server).
- Conectores: A:R -- L:B con doble guión. NUNCA uses --> (es sintaxis de flowchart).
- Iconos válidos en Mermaid 11: cloud, database, disk, internet, server.

## Ejemplo técnico mínimo
Incluye un ejemplo de uso verificable de la API pública cuando sea posible.
Debe usar datos ficticios seguros y no requerir credenciales reales.

---

Restricciones:
- SOLO incluye lo exportado públicamente, no implementación interna
- El diagrama debe ser Mermaid válido en bloque fenced `mermaid`
- No inventes firmas, excepciones, tipos, dependencias ni efectos secundarios
- Si falta información, añade "Pendiente de verificación" con puntos concretos
- NO uses la directiva --8<-- para incluir código; embebe el código directamente en los bloques fenced
- Responde SOLO con el Markdown
```
## Criterios de selección de diagrama por tipo de módulo

| Tipo de módulo | Diagrama recomendado | Motivo |
|---|---|---|
| Módulo con excepciones y data classes base | `classDiagram` | Jerarquía de tipos exportados |
| Pipeline de validación y filtrado de archivos | `flowchart TD` | Lógica de decisión encadenada |
| Generación de múltiples tipos de archivo | `flowchart TD` | Selección y pipeline de transformación |
| Motor de personalización con sustituciones | `flowchart TD` | Pipeline: leer → aplicar → escribir |
| Orquestador con múltiples fases | `sequenceDiagram` | Flujo completo con actores y salidas |
| Módulo con Web API / base de datos / Docker | `architecture-beta` | Topología de infraestructura física |

## Cómo usar este prompt

### Modo módulo único — Claude Code

```
Lee el archivo [ruta_del_módulo] y genera documentación técnica con diagrama Mermaid
usando el prompt en .github/prompts/technical_doc.prompt.md.
Guarda el resultado en docs/api/[nombre_módulo].md y actualiza mkdocs.yml.
```

Ejemplo concreto:

```
Lee src/util_bbdd/timelog/project_loader.py y genera documentación técnica
usando .github/prompts/technical_doc.prompt.md.
Tipo de diagrama: sequenceDiagram.
Guarda en docs/api/project-manager.md y añade la entrada en mkdocs.yml bajo "Técnica:".
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

Markdown con las 6 secciones obligatorias (más `Arquitectura física` si aplica), incluyendo
un bloque `mermaid` válido que se renderiza correctamente en MkDocs Material y en GitHub.
Todo el contenido derivado del código real: sin inventar parámetros, retornos ni comportamientos.
