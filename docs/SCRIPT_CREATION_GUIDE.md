# Guía de Creación de Scripts

Esta guía explica cómo crear nuevos scripts para el dashboard de procesamiento de datos.

## Estructura de un Script

Todo script debe:

1. **Heredar de `BaseScript`**
2. **Usar el decorador `@register_script`**
3. **Definir metadatos** (name, description, category)
4. **Implementar `get_queries()`** - Las consultas SOQL
5. **Implementar `process()`** - La lógica de procesamiento

## Ejemplo Básico

```python
from core.base_script import BaseScript, ScriptResult, ScriptMetrics
from core.script_registry import register_script

@register_script
class MiScript(BaseScript):
    name = "Mi Script de Ejemplo"
    description = "Detecta X situación en los datos"
    category = "Regularización"
    version = "1.0"
    author = "Mi Nombre"
    
    supports_preview = True
    supports_update = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        limit = "LIMIT 100" if preview else ""
        return [f"SELECT Id, Name FROM Account {limit}"]
    
    def process(self, query_results: dict) -> ScriptResult:
        df = query_results['query_0']
        
        metrics = ScriptMetrics(total_records=len(df))
        metrics.add_metric('total', len(df), 'Total Cuentas', '📋')
        
        return ScriptResult(success=True, data=df, metrics=metrics)
```

## Metadatos del Script

| Atributo | Descripción | Ejemplo |
|----------|-------------|---------|
| `name` | Nombre mostrado en la UI | `"Contratos sin Asset"` |
| `description` | Descripción breve | `"Detecta contratos huérfanos"` |
| `category` | Categoría para agrupar | `"Regularización"` |
| `version` | Versión del script | `"1.0"` |
| `author` | Autor | `"AG"` |

### Opciones de Ejecución

| Atributo | Descripción | Default |
|----------|-------------|---------|
| `supports_preview` | Permite modo vista previa | `True` |
| `supports_update` | Permite actualizaciones | `False` |
| `requires_confirmation` | Confirmar antes de updates | `True` |

## Métodos Requeridos

### `get_queries(preview: bool) -> list[str]`

Retorna las consultas SOQL necesarias.

```python
def get_queries(self, preview: bool = False) -> list[str]:
    limit = "LIMIT 500" if preview else ""
    
    return [
        f"SELECT Id, Name FROM Account {limit}",
        "SELECT Id, AccountId FROM Contact"
    ]
```

**Tips:**
- Usar `preview` para limitar resultados en pruebas
- Cada query se ejecuta con Bulk API
- Los resultados están en `query_0`, `query_1`, etc.

### `process(query_results: dict) -> ScriptResult`

Procesa los datos y retorna el resultado.

```python
def process(self, query_results: dict) -> ScriptResult:
    df_accounts = query_results['query_0']
    df_contacts = query_results['query_1']
    
    # Procesamiento
    merged = df_accounts.merge(df_contacts, ...)
    
    # Métricas
    metrics = ScriptMetrics(total_records=len(merged))
    metrics.add_metric('total', len(merged), 'Total', '📊')
    
    # Warnings
    self.add_warning("Mensaje de advertencia")
    
    # Datos intermedios (para debugging)
    self.store_intermediate('merged_raw', merged)
    
    return ScriptResult(
        success=True,
        data=merged,
        metrics=metrics
    )
```

## Métodos Opcionales

### `get_column_config() -> list[ColumnConfig]`

Define cómo mostrar las columnas en la tabla.

```python
from core.base_script import ColumnConfig, ColumnType

def get_column_config(self) -> list[ColumnConfig]:
    return [
        ColumnConfig('Id', 'ID', ColumnType.TEXT, visible=False),
        ColumnConfig('Name', 'Nombre', ColumnType.TEXT),
        ColumnConfig('Status', 'Estado', ColumnType.STATUS),
        ColumnConfig('Amount', 'Importe', ColumnType.CURRENCY),
        ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
    ]
```

**ColumnType disponibles:**
- `TEXT` - Texto normal
- `NUMBER` - Número
- `DATE` - Fecha
- `DATETIME` - Fecha y hora
- `STATUS` - Estado (con colores)
- `LINK` - Enlace clickeable
- `BOOLEAN` - Sí/No
- `CURRENCY` - Moneda

### `get_groupby_options() -> list[str]`

Columnas disponibles para agrupar en el análisis.

```python
def get_groupby_options(self) -> list[str]:
    return ['Status', 'Type', 'Region']
```

### `detect_anomalies(data: DataFrame) -> DataFrame`

Detecta registros anómalos.

```python
def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
    # Filtrar anomalías
    anomalies = data[data['Status'] == 'ERROR'].copy()
    
    # Añadir clasificación
    anomalies['anomaly_type'] = 'Tipo de anomalía'
    anomalies['anomaly_severity'] = 'Alta'  # Alta, Media, Baja
    
    return anomalies
```

### `get_update_operations() -> list[dict]`

Define operaciones de actualización (solo si `supports_update=True`).

```python
def get_update_operations(self) -> list[dict]:
    return [
        {
            'name': 'activate',
            'description': 'Activar registros',
            'fields': {'Status': 'Active'}
        },
        {
            'name': 'deactivate',
            'description': 'Desactivar registros',
            'fields': {'Status': 'Inactive'}
        }
    ]
```

### `execute_update(operation: str, data: DataFrame) -> tuple`

Ejecuta una operación de actualización.

```python
def execute_update(self, operation: str, data: pd.DataFrame) -> tuple[list, list]:
    if operation == 'activate':
        records = [{'Id': row['Id'], 'Status': 'Active'} for _, row in data.iterrows()]
        return self.sf_client.bulk_update('Account', records)
    
    raise ValueError(f"Operación desconocida: {operation}")
```

## Clase ScriptResult

```python
@dataclass
class ScriptResult:
    success: bool = True
    data: pd.DataFrame = None           # Datos principales
    metrics: ScriptMetrics = None       # KPIs
    intermediate_data: dict = {}        # Datos intermedios
    anomalies: pd.DataFrame = None      # Anomalías detectadas
    error_message: str = None           # Mensaje de error
    warnings: list = []                 # Advertencias
    execution_time: float = 0.0         # Tiempo de ejecución
```

## Clase ScriptMetrics

```python
metrics = ScriptMetrics(
    total_records=100,
    processed_records=95,
    success_count=90,
    error_count=5
)

# Añadir métricas personalizadas
metrics.add_metric(
    key='unique_key',
    value=42,
    label='Etiqueta en UI',
    icon='📊'
)
```

## Acceso al Cliente Salesforce

El cliente está disponible en `self.sf_client`:

```python
# Query simple (REST API)
results = self.sf_client.query("SELECT Id FROM Account LIMIT 10")

# Query bulk (para grandes volúmenes)
results = self.sf_client.bulk_query("SELECT Id FROM Account")

# Update bulk
success, failed = self.sf_client.bulk_update('Account', records)

# Insert bulk
success, failed = self.sf_client.bulk_insert('Account', records)

# Describe object
metadata = self.sf_client.describe_object('Account')

# Picklist values
values = self.sf_client.get_picklist_values('Account', 'Status')
```

## Buenas Prácticas

1. **Limitar queries en preview** - Usar `LIMIT` cuando `preview=True`
2. **Guardar datos intermedios** - Usar `store_intermediate()` para debugging
3. **Añadir warnings** - Usar `add_warning()` para mensajes importantes
4. **Documentar el script** - Docstrings claros en la clase
5. **Validar datos** - Manejar DataFrames vacíos
6. **Usar constantes** - Definir códigos de estado como constantes de clase
7. **Métricas útiles** - Añadir KPIs relevantes para el análisis

## Ubicación de Archivos

Los scripts deben ir en:
```
dashboard/scripts/mi_nuevo_script.py
```

Y añadir el import en `dashboard/scripts/__init__.py`:
```python
from . import mi_nuevo_script
```

## Template

Usa el archivo `_template.py` como punto de partida para nuevos scripts.
