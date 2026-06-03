# Auditoría de Operaciones Bulk

## 1. Descripción General

Registra automáticamente cada operación de datos masiva (INSERT, UPDATE, DELETE en lote) en un fichero CSV persistente, permitiendo rastrear qué proceso tocó qué tabla, cuándo, cuántos registros afectó y si la operación fue exitosa o falló.

Proporciona análisis básico del historial (estadísticas por tabla, filtrado por fecha, resumen de errores) y exportación a Excel, JSON o HTML para reportes de auditoría o revisiones de calidad de datos.

**Precondiciones:**

- Directorio de salida accesible con permisos de escritura para el fichero CSV de auditoría
- Librería `pandas` instalada (requerida para el registro y exportación)
- Para exportación Excel: `openpyxl` instalado
- Si se usa con operaciones bulk, el gestor de auditoría se configura antes de iniciar las operaciones

## 2. Reglas de Negocio

| Regla | Descripción | Impacto si se viola |
|---|---|---|
| Context manager obligatorio | Las operaciones se registran correctamente solo dentro de un bloque `with AuditTransaction(...)` | Operaciones fuera del context manager no se escriben al CSV ni al historial |
| Registro en caso de error | Si la operación falla, el error se captura y se registra igualmente (con `exito=False`) | El historial refleja intentos fallidos, permitiendo identificar tablas problemáticas |
| CSV como fuente persistente | El registro se escribe en CSV al finalizar cada transacción, independientemente de lo que haga el llamador | El CSV sobrevive a reinicios del proceso; el historial en memoria no |
| Invalidación de caché en éxito | Si el caché está activo en el manager, se invalida al completar la transacción exitosamente | Sin invalidación, consultas posteriores al bulk pueden devolver datos desactualizados |
| Nombre de transacción obligatorio | Se rechaza un nombre de transacción vacío o compuesto solo de espacios | Facilita la trazabilidad: cada operación registrada tiene identificador legible |

## 3. Casos de Uso

### Flujo principal

```mermaid
sequenceDiagram
    actor ETL as Proceso ETL
    participant AM as Gestor de Auditoría
    participant CSV as Fichero CSV
    participant Exp as Exportador

    ETL->>AM: Inicializar con ruta CSV
    ETL->>AM: Iniciar transacción con nombre descriptivo
    Note over AM: Registra inicio de transacción

    ETL->>AM: Registrar operaciones (tabla, filas, tipo)
    ETL->>AM: Finalizar transacción (éxito o error)
    AM->>CSV: Registrar (timestamp, tabla, filas, duración, estado)

    opt Auditoría periódica
        ETL->>AM: Obtener resumen estadístico
        AM-->>ETL: Estadísticas por tabla y motor
        ETL->>AM: Exportar a Excel
        AM->>Exp: Generar Excel con historial filtrado
        Exp-->>ETL: Fichero .xlsx generado
    end
```

### Flujos alternativos

**Operación con error:** Si la operación bulk falla, el gestor de auditoría captura la excepción y la registra con `exito=False`. El flujo continúa; no se pierde el registro del intento fallido.

**Análisis de historial:** El usuario puede consultar estadísticas sin realizar nuevas operaciones — filtrado por fecha, por tabla, o exportación del historial completo en Excel, JSON o HTML.

**Límites y exclusiones:**

- Solo registra metadatos de la operación (tabla, tipo, filas, duración): no guarda los datos modificados
- El CSV de auditoría puede crecer sin límite: la rotación o limpieza del fichero es responsabilidad del operador
- No integra con sistemas de auditoría externos (Splunk, ELK, CloudWatch): solo produce ficheros locales
- No garantiza atomicidad del registro: si el proceso se interrumpe durante la escritura al CSV, la entrada puede quedar corrupta
- No cifra ni protege el CSV de auditoría: tratar el fichero como información sensible si los nombres de tabla son confidenciales

## 4. Glosario y Términos

| Término | Definición |
|---|---|
| Transacción de auditoría | Unidad lógica de seguimiento que agrupa una o más operaciones bulk bajo un nombre descriptivo |
| CSV de auditoría | Fichero de texto delimitado por comas donde se persiste el historial de operaciones bulk |
| `exito=False` | Indicador en el registro que señala que la operación falló; la fila sigue existiendo en el CSV |
