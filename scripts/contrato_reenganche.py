"""
Script: Contrato Reenganche

Detecta contratos que necesitan proceso de reenganche
(reconexión después de corte o suspensión).
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import CONTRACT_STATUS_MAP, ASSET_STATUS_MAP


@register_script
class ContratoReenganche(BaseScript):
    """
    Detecta contratos pendientes de reenganche.
    """
    
    name = "Contratos - Reenganche"
    description = "Detecta contratos pendientes de proceso de reenganche"
    category = "Extracción de datos"  
    version = "3.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Asset status for cut/suspended
    ASSET_STATUS_CORTADO = '08'
    ASSET_STATUS_SUSPENDIDO = '09'
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for contracts needing reenganche."""
        limit_clause = "LIMIT 2000" if preview else ""
        
        # Query: Active contracts with asset in cortado/suspendido
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c,
                   acn_fld_Contract__r.ContractNumber,
                   acn_fld_Contract__r.Status,
                   acn_fld_Contract__r.NewCo_ServiceAccount__r.Name,
                   CreatedDate, LastModifiedDate
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND Status IN ('{self.ASSET_STATUS_CORTADO}', '{self.ASSET_STATUS_SUSPENDIDO}')
            AND acn_fld_Contract__r.Status = '02'
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find contracts pending reenganche."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        # Enrich with status labels
        df['AssetStatusLabel'] = df['Status'].map(ASSET_STATUS_MAP)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df))
        
        # Count by asset status
        cortados = len(df[df['Status'] == self.ASSET_STATUS_CORTADO])
        suspendidos = len(df[df['Status'] == self.ASSET_STATUS_SUSPENDIDO])
        
        metrics.add_metric(
            'total_pending',
            len(df),
            'Pendientes Reenganche',
            '⚠️' if len(df) > 0 else '✅'
        )
        
        metrics.add_metric(
            'cortados',
            cortados,
            'Cortados',
            '🔴' if cortados > 0 else '✅'
        )
        
        metrics.add_metric(
            'suspendidos',
            suspendidos,
            'Suspendidos',
            '🟡' if suspendidos > 0 else '✅'
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
            ColumnConfig('AssetStatusLabel', 'Estado Asset', ColumnType.STATUS),
            ColumnConfig('acn_fld_Contract__r.NewCo_ServiceAccount__r.Name', 'Service Account', ColumnType.TEXT),
            ColumnConfig('LastModifiedDate', 'Última Modificación', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['AssetStatusLabel', 'Status']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All pending reenganche are potential anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Pendiente Reenganche'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'AssetStatusLabel',
                'title': 'Por Estado de Asset'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'process_reenganche',
                'description': 'Procesar reenganche - cambiar estado a Activo',
                'fields': {
                    'Status': '03',
                    'vlocity_cmt__ProvisioningStatus__c': 'Active'
                }
            }
        ]
