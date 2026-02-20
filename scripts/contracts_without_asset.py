"""
Script: Contratos sin Asset

Detecta contratos que no tienen ningún asset asociado.
Esto puede indicar un problema de integridad de datos.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import CONTRACT_STATUS_MAP


@register_script
class ContractsSinAsset(BaseScript):
    """
    Detecta contratos sin assets asociados.
    """
    
    name = "Contratos sin Asset"
    description = "Detecta contratos que no tienen ningún asset asociado"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for contracts without assets."""
        limit_clause = "LIMIT 500" if preview else ""
        
        query = f"""
            SELECT Id, ContractNumber, Status, NewCo_ServiceAccount__c,
                   NewCo_ServiceAccount__r.Name, CreatedDate, LastModifiedDate,
                   StartDate, EndDate
            FROM Contract
            WHERE Id NOT IN (
                SELECT acn_fld_Contract__c 
                FROM Asset 
                WHERE acn_fld_Contract__c != null
            )
            AND NewCo_ServiceAccount__c != null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process contracts without assets."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        # Enrich with status labels
        df['StatusLabel'] = df['Status'].map(CONTRACT_STATUS_MAP)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df))
        
        # Count by status
        status_counts = df['Status'].value_counts()
        for status, count in status_counts.items():
            label = CONTRACT_STATUS_MAP.get(status, status)
            metrics.add_metric(
                f'status_{status}',
                count,
                f'En {label}',
                '📊'
            )
        
        # Active contracts without asset (most critical)
        active_count = len(df[df['Status'] == '02'])
        metrics.add_metric(
            'active_without_asset',
            active_count,
            'Activos sin Asset',
            '🔴' if active_count > 0 else '✅'
        )
        
        return ScriptResult(
            success=True,
            data=df,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('ContractNumber', 'Nº Contrato', ColumnType.TEXT),
            ColumnConfig('StatusLabel', 'Estado', ColumnType.STATUS),
            ColumnConfig('NewCo_ServiceAccount__r.Name', 'Service Account', ColumnType.TEXT),
            ColumnConfig('StartDate', 'Fecha Inicio', ColumnType.DATE),
            ColumnConfig('EndDate', 'Fecha Fin', ColumnType.DATE),
            ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['StatusLabel', 'Status']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """Active contracts without assets are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        # Only active contracts are real anomalies
        anomalies = data[data['Status'] == '02'].copy()
        
        if anomalies.empty:
            return pd.DataFrame()
        
        anomalies['anomaly_type'] = 'Contrato Activo sin Asset'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'StatusLabel',
                'title': 'Distribución por Estado'
            },
            {
                'type': 'bar',
                'x': 'StatusLabel',
                'title': 'Contratos por Estado'
            }
        ]
