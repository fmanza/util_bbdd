# Registro de Queries

## 1. Descripción General

Centraliza todas las consultas SQL predefinidas de la librería en un único fichero JSON (`sql_queries.json`), organizadas por motor de base de datos. Cualquier componente que necesite ejecutar una query específica del motor la solicita por nombre; el sistema valida los parámetros y devuelve el SQL final listo para ejecutar, sin exponer el texto SQL en el código de aplicación.

Esto facilita el mantenimiento de queries multi-motor: cambiar la query de PostgreSQL para listar tablas no afecta al código que la invoca, solo al fichero JSON.

**Precondiciones:**

- Fichero `sql_queries.json` accesible en la ruta por defecto del paquete (`data/sql_queries.json`) o en una ruta personalizada
- Tipo de motor declarado y reconocido por la librería
- Parámetros necesarios para la query conocidos por el llamador

## 2. Reglas de Negocio

| Regla | Descripción | Impacto si se viola |
|---|---|---|
| Carga única en init | El registro carga el JSON completo al inicializarse; no recarga durante la sesión | Cambios al JSON en tiempo de ejecución no se reflejan sin reiniciar el registro |
| Queries por motor | Cada query está definida bajo su clave de motor; no hay queries genéricas | Solicitar una query para un motor que no la tiene lanza error de query no encontrada |
| Validación antes de interpolación | Los parámetros se validan antes de construir el SQL | Parámetros faltantes o incorrectos se detectan antes de ir a BD; el error es claro y tiene contexto |
| Sin excepciones en validadores | Los validadores retornan `(False, [mensaje])` en lugar de lanzar excepciones | Un validador que lanza excepción rompe el flujo del resolver sin mensaje útil |
| Interpolación segura | Los parámetros son identificadores (nombres de BD, tabla), no valores de datos de usuario | Usar parámetros de usuario en templates SQL sin sanitizar introduce riesgo de inyección SQL |

## 3. Casos de Uso

### Flujo principal

```mermaid
sequenceDiagram
    actor Mgr as Gestor (Sync o Async)
    participant Res as Resolvedor de Queries
    participant Reg as Registro de Queries
    participant Val as Validador de Motor
    participant JSON as sql_queries.json

    Mgr->>Res: Resolver query por nombre y parámetros
    Res->>Reg: Obtener definición (motor, nombre)
    Reg->>JSON: Leer template SQL (cargado en init)
    JSON-->>Reg: Template SQL con placeholders
    Reg-->>Res: Definición (template, parámetros requeridos)

    Res->>Val: Validar parámetros proporcionados
    Val-->>Res: (válido=True, avisos=[])

    Res->>Res: Interpolar parámetros en template
    Res-->>Mgr: SQL final validado
```

### Flujos alternativos

**Query no encontrada:** Si se solicita una query para un motor que no la tiene definida, el resolvedor devuelve un error claro indicando el nombre y el motor buscados.

**Parámetros inválidos:** El validador devuelve `(False, [lista de avisos])` en lugar de lanzar excepción. El resolvedor decide si bloquear la ejecución o continuar con advertencias, según el contexto.

**Límites y exclusiones:**

- No ejecuta las queries: solo resuelve el SQL final; la ejecución es responsabilidad del executor del gestor
- No cachea queries resueltas: cada llamada valida e interpola de nuevo
- No soporta queries dinámicas (construcción condicional de cláusulas WHERE): los templates son estáticos con placeholders fijos
- Los parámetros interpolados son identificadores, no valores de datos: para valores de usuario usar consultas libres con parámetros bind de SQLAlchemy

## 4. Glosario y Términos

| Término | Definición |
|---|---|
| Template SQL | Texto SQL almacenado en `sql_queries.json` con placeholders para parámetros, por ejemplo `{database}` |
| Interpolación | Proceso de sustituir los placeholders del template por los valores reales de los parámetros |
| Query por nombre | Consulta SQL identificada por una clave string (`"obtener_tablas"`) en lugar de por su texto SQL literal |
