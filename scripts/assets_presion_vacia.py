"""
Script: Assets - Presión Vacía

Detecta assets de gas que no tienen el campo de presión informado
cuando debería estarlo según su configuración.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetsPresionVacia(BaseScript):
    """
    Detecta assets de gas sin presión informada.
    """
    
    name = "Assets Gas - Presión Vacía"
    description = "Detecta assets de gas sin campo de presión informado"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for gas assets without pressure."""
        limit_clause = "LIMIT 2000" if preview else ""
        
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c,
                   acn_fld_Contract__r.ContractNumber,
                   acn_fld_Contract__r.acn_fld_BusinessDivision__c,
                   acn_fld_Contract__r.acn_fld_CUPS__r.Name,
                   NewCo_Presion__c, ProductFamily,
                   CreatedDate
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND Status = '03'
            AND ProductFamily = 'Gas'
            AND NewCo_Presion__c = null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process gas assets without pressure."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        # Enrich with status labels
        df['StatusLabel'] = df['Status'].map(ASSET_STATUS_MAP)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df))
        
        metrics.add_metric(
            'gas_without_pressure',
            len(df),
            'Sin Presión',
            '🔴' if len(df) > 0 else '✅'
        )
        
        return ScriptResult(
            success=True,
            data=df,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('Name', 'Asset', ColumnType.TEXT),
            ColumnConfig('acn_fld_Contract__r.ContractNumber', 'Contrato', ColumnType.TEXT),
            ColumnConfig('acn_fld_Contract__r.acn_fld_CUPS__r.Name', 'CUPS', ColumnType.TEXT),
            ColumnConfig('StatusLabel', 'Estado', ColumnType.STATUS),
            ColumnConfig('ProductFamily', 'Familia', ColumnType.TEXT),
            ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['StatusLabel']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All gas assets without pressure are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Asset Gas sin Presión'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'bar',
                'x': 'StatusLabel',
                'title': 'Por Estado'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'set_pressure',
                'description': 'Establecer presión desde datos del Service Point',
                'fields': {
                    'NewCo_Presion__c': '(valor del SP)'
                }
            }
        ]
