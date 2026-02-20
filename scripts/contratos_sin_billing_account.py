"""
Script: Contratos sin Billing Account

Detecta contratos que no tienen una Billing Account asociada.
Esto puede causar problemas en la facturación.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import CONTRACT_STATUS_MAP


@register_script
class ContratosSinBillingAccount(BaseScript):
    """
    Detecta contratos sin billing account.
    """
    
    name = "Contratos sin Billing Account"
    description = "Detecta contratos sin cuenta de facturación asociada"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for contracts without billing account."""
        limit_clause = "LIMIT 1000" if preview else ""
        
        query = f"""
            SELECT Id, ContractNumber, Status, NewCo_ServiceAccount__c,
                   NewCo_ServiceAccount__r.Name, vlocity_cmt__BillingAccountId__c,
                   CreatedDate, StartDate, EndDate
            FROM Contract
            WHERE vlocity_cmt__BillingAccountId__c = null
            AND Status IN ('01', '02')
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process contracts without billing account."""
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
        
        # Active contracts without billing account (critical)
        active_count = len(df[df['Status'] == '02'])
        metrics.add_metric(
            'active_without_billing',
            active_count,
            'Activos sin Billing',
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
            ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['StatusLabel', 'Status']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """Active contracts without billing are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data[data['Status'] == '02'].copy()
        
        if anomalies.empty:
            return pd.DataFrame()
        
        anomalies['anomaly_type'] = 'Contrato Activo sin Billing Account'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'StatusLabel',
                'title': 'Distribución por Estado'
            }
        ]
