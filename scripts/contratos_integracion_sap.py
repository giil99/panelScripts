"""
Script: Contratos Activos - Integración SAP

Detecta contratos activos que necesitan ser enviados a SAP
o que tienen problemas pendientes de integración.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import CONTRACT_STATUS_MAP


@register_script
class ContratosActivosIntegracionSAP(BaseScript):
    """
    Detecta contratos activos pendientes de integración SAP.
    """
    
    name = "Contratos - Integración SAP"
    description = "Detecta contratos activos pendientes de envío a SAP"
    category = "Extracción de datos"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for contracts pending SAP integration."""
        limit_clause = "LIMIT 2000" if preview else ""
        
        query = f"""
            SELECT Id, ContractNumber, Status, 
                   NewCo_ServiceAccount__c, NewCo_ServiceAccount__r.Name,
                   acn_fld_CUPS__c, acn_fld_CUPS__r.Name,
                   acn_fld_BusinessDivision__c,
                   NewCo_IntegracionSAP__c, NewCo_FechaEnvioSAP__c,
                   CreatedDate, StartDate, ActivatedDate
            FROM Contract
            WHERE Status = '02'
            AND (NewCo_IntegracionSAP__c = null OR NewCo_IntegracionSAP__c = false)
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process contracts pending SAP integration."""
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
        
        metrics.add_metric(
            'pending_sap',
            len(df),
            'Pendientes SAP',
            '🔴' if len(df) > 0 else '✅'
        )
        
        # Count by business division
        if 'acn_fld_BusinessDivision__c' in df.columns:
            div_counts = df['acn_fld_BusinessDivision__c'].value_counts()
            for div, count in div_counts.items():
                if div:
                    metrics.add_metric(
                        f'div_{div}',
                        count,
                        f'División: {div}',
                        '📊'
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
            ColumnConfig('acn_fld_CUPS__r.Name', 'CUPS', ColumnType.TEXT),
            ColumnConfig('acn_fld_BusinessDivision__c', 'División', ColumnType.TEXT),
            ColumnConfig('ActivatedDate', 'Fecha Activación', ColumnType.DATETIME),
            ColumnConfig('NewCo_FechaEnvioSAP__c', 'Enviado SAP', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['acn_fld_BusinessDivision__c']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """Contracts not sent to SAP are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Pendiente Integración SAP'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'acn_fld_BusinessDivision__c',
                'title': 'Pendientes por División'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'send_to_sap',
                'description': 'Enviar contratos a SAP (ejecutar evento G4_04)',
                'fields': {}
            }
        ]
