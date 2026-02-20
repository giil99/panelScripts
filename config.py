"""
Configuración global del dashboard.
"""
import os
from pathlib import Path

# Rutas base
BASE_DIR = Path(__file__).parent
EXPORTS_DIR = BASE_DIR / "exports"
SCRIPTS_DIR = BASE_DIR / "scripts"

# Crear directorios si no existen
EXPORTS_DIR.mkdir(exist_ok=True)

# Salesforce configuration
SF_API_VERSION = "62.0"
SF_CREDENTIALS_PATH = BASE_DIR.parent / "salesforce_credentials.json"

# UI Configuration
APP_TITLE = "Naturgy Data Scripts Dashboard"
APP_ICON = "⚡"
PAGE_LAYOUT = "wide"

# Default poll interval for bulk operations (seconds)
BULK_POLL_INTERVAL = 15

# Status mappings (Salesforce picklist values to Spanish labels)
CONTRACT_STATUS_MAP = {
    "01": "Pendiente",
    "02": "Activado",
    "03": "Inactivo",
    "04": "Baja",
    "05": "Cancelado",
    "06": "Finalizado"
}

ASSET_STATUS_MAP = {
    "01": "Borrador",
    "02": "Alta en curso",
    "03": "Activado",
    "04": "Modificación en curso",
    "05": "En proceso de desconexión",
    "06": "Baja en curso",
    "08": "Cortado",
    "09": "Suspendido",
    "10": "Atípico",
    "13": "Cancelado",
    "14": "Baja",
    "15": "Rechazado",
    "28": "Inactivo"
}

CONTRACT_REQUEST_STATUS_MAP = {
    "01": "Nuevo",
    "02": "En proceso",
    "03": "Aceptado",
    "04": "Rechazado",
    "05": "Cancelado",
    "06": "Activado"
}

# Categories for script organization
SCRIPT_CATEGORIES = [
    "Regularización",
    "Detección de inconsistencias",
    "Extracción de datos",
    "Métricas operativas",
    "Mantenimiento"
]

# Chart theme
CHART_THEME = "plotly_white"
CHART_COLORS = [
    "#3B82F6",  # Blue
    "#06B6D4",  # Cyan
    "#F59E0B",  # Amber
    "#10B981",  # Green
    "#8B5CF6",  # Purple
    "#EF4444",  # Red
    "#EC4899",  # Pink
    "#F97316",  # Orange
    "#14B8A6",  # Teal
    "#64748B"   # Slate
]
