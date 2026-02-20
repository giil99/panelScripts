# Naturgy Data Scripts Dashboard

Interfaz gráfica modular para ejecutar, visualizar y analizar scripts de procesamiento de datos de Salesforce.

## 🚀 Instalación

```bash
cd "c:\Users\agilsole@deloitte.es\Naturgy\Naturgy Bitbucket\manifest\Scripts AG\dashboard"
pip install -r requirements.txt
```

## ▶️ Ejecución

```bash
streamlit run app.py
```

O si `streamlit` no está en PATH:
```bash
python -m streamlit run app.py
```

**La aplicación se abrirá automáticamente en tu navegador en http://localhost:8501**

## 📁 Estructura del Proyecto

```
dashboard/
├── app.py                      # Entrada principal Streamlit
├── requirements.txt            # Dependencias
├── config.py                   # Configuración global
│
├── core/                       # Núcleo del framework
│   ├── __init__.py
│   ├── base_script.py          # Clase base para scripts
│   ├── script_registry.py      # Registro de scripts disponibles
│   └── execution_engine.py     # Motor de ejecución
│
├── data/                       # Capa de datos
│   ├── __init__.py
│   ├── salesforce_client.py    # Cliente Salesforce
│   └── bulk_api.py             # Operaciones Bulk API
│
├── visualization/              # Componentes de visualización
│   ├── __init__.py
│   ├── tables.py               # Tablas dinámicas
│   ├── charts.py               # Gráficos (barras, líneas, pie, etc.)
│   ├── kpis.py                 # Panel de KPIs
│   └── filters.py              # Filtros dinámicos
│
├── pages/                      # Páginas de Streamlit
│   ├── __init__.py
│   ├── home.py                 # Página principal y conexión
│   ├── script_execution.py     # Ejecución y visualización de resultados
│   └── history.py              # Historial de ejecuciones
│
├── scripts/                    # Scripts adaptados (adaptadores)
│   ├── __init__.py
│   ├── contratos_activos_cortados.py
│   ├── contratos_inactivos_status.py
│   └── contracts_without_asset.py
│
└── exports/                    # Exportaciones CSV/Excel
```

## 🔧 Cómo añadir un nuevo script

1. Crear archivo en `scripts/` heredando de `BaseScript`
2. Implementar los métodos requeridos
3. Registrar el script en `script_registry.py`

```python
from core.base_script import BaseScript, ScriptResult

class MiNuevoScript(BaseScript):
    name = "Mi Nuevo Script"
    description = "Descripción del script"
    category = "Regularización"
    
    def get_queries(self) -> list[str]:
        return ["SELECT Id FROM Account LIMIT 10"]
    
    def process(self, data: dict) -> ScriptResult:
        # Lógica de procesamiento
        return ScriptResult(data=df, metrics={...})
```

## 📊 Características

- ✅ Ejecución de scripts desde la interfaz
- ✅ Visualización detallada de resultados en la misma página
- ✅ Filtros dinámicos multi-campo
- ✅ Agrupación y análisis por columnas
- ✅ KPIs y métricas agregadas
- ✅ Gráficos interactivos (Plotly)
- ✅ Exportación CSV/Excel
- ✅ Detección de anomalías
- ✅ Interfaz simplificada y directa
"# panelScripts" 
