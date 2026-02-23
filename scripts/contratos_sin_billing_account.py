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
        
        # IMPORTANTE: Usar NewCo_BillingAccount__c (como en notebook original)
        # NO filtrar por Status en la query (filtrar después en process)
        query = f"""
            SELECT Id, ContractNumber, Status, NewCo_BillingAccount__c,
                   acn_fld_ContractCode2__c, NewCo_ServiceAccount__c,
                   NewCo_ServiceAccount__r.Name, CreatedDate, StartDate, EndDate
            FROM Contract
            WHERE NewCo_BillingAccount__c = null
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
        
        # LÓGICA DEL NOTEBOOK: Filtrar solo contratos activos (Status = '02') DESPUÉS de la query
        df_activos = df[df['Status'] == '02'].copy()
        
        # Si no hay contratos activos, devolver vacío
        if df_activos.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(
                    total_records=0,
                    message=f"Total contratos sin billing: {len(df)}, activos: 0"
                )
            )
        
        # Enrich with status labels (solo activos)
        df_activos['StatusLabel'] = df_activos['Status'].map(CONTRACT_STATUS_MAP)
        
        # Calculate metrics (como en notebook)
        total_sin_billing = len(df)
        total_activos = len(df_activos)
        
        metrics = ScriptMetrics(
            total_records=total_activos,
            message=f"Total contratos sin billing: {total_sin_billing}, activos: {total_activos}"
        )
        
        metrics.add_metric(
            'total_sin_billing',
            total_sin_billing,
            'Sin Billing Account',
            '📊'
        )
        
        metrics.add_metric(
            'active_without_billing',
            total_activos,
            'Activos sin Billing',
            '🔴' if total_activos > 0 else '✅'
        )
        
        return ScriptResult(
            success=True,
            data=df_activos,  # Retornar solo activos como en notebook
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('acn_fld_ContractCode2__c', 'Contract Code', ColumnType.TEXT),
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
