"""
Script: Contratos - Múltiples Assets en Baja

Detecta contratos que tienen múltiples assets en estado baja,
lo cual puede indicar un problema de datos.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class ContractsMultipleAssetBaja(BaseScript):
    """
    Detecta contratos con múltiples assets en estado baja.
    """
    
    name = "Contratos - Múltiples Assets Baja"
    description = "Detecta contratos con más de un asset en estado baja"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    # Status codes for "baja" states
    BAJA_STATUSES = ['06', '13', '14', '15', '28']  # Baja en curso, Cancelado, Baja, Rechazado, Inactivo
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets in baja status."""
        limit_clause = "LIMIT 5000" if preview else ""
        baja_status_str = "','".join(self.BAJA_STATUSES)
        
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c, 
                   acn_fld_Contract__r.ContractNumber,
                   CreatedDate, acn_fld_EndDateVersion__c
            FROM Asset 
            WHERE Status IN ('{baja_status_str}')
            AND vlocity_cmt__ParentItemId__c = NULL 
            AND acn_fld_Contract__c != null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find contracts with multiple baja assets."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Group by contract
        grouped = df.groupby('acn_fld_Contract__c').agg({
            'Id': 'count',
            'Name': lambda x: '; '.join(x.astype(str)),
            'Status': lambda x: '; '.join(x.astype(str)),
            'acn_fld_Contract__r.ContractNumber': 'first',
            'CreatedDate': 'min'
        }).reset_index()
        
        grouped.columns = [
            'ContractId', 'AssetCount', 'AssetNames', 'AssetStatuses',
            'ContractNumber', 'OldestCreatedDate'
        ]
        
        # Filter only those with more than one
        multiple_baja = grouped[grouped['AssetCount'] > 1].copy()
        
        # Add status labels
        def get_status_labels(statuses_str):
            statuses = statuses_str.split('; ')
            labels = [ASSET_STATUS_MAP.get(s.strip(), s.strip()) for s in statuses]
            return '; '.join(labels)
        
        if not multiple_baja.empty:
            multiple_baja['StatusLabels'] = multiple_baja['AssetStatuses'].apply(get_status_labels)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(multiple_baja))
        
        metrics.add_metric(
            'contracts_with_multiple_baja',
            len(multiple_baja),
            'Contratos Afectados',
            '⚠️' if len(multiple_baja) > 0 else '✅'
        )
        
        # Count by number of assets
        if not multiple_baja.empty:
            count_distribution = multiple_baja['AssetCount'].value_counts().sort_index()
            for count, num in count_distribution.items():
                if count <= 5:
                    metrics.add_metric(
                        f'with_{count}_baja',
                        num,
                        f'Con {count} assets baja',
                        '📊'
                    )
        
        return ScriptResult(
            success=True,
            data=multiple_baja,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('ContractNumber', 'Nº Contrato', ColumnType.TEXT),
            ColumnConfig('AssetCount', 'Nº Assets Baja', ColumnType.NUMBER),
            ColumnConfig('StatusLabels', 'Estados', ColumnType.TEXT),
            ColumnConfig('AssetNames', 'Assets', ColumnType.TEXT),
            ColumnConfig('OldestCreatedDate', 'Más Antiguo', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['AssetCount']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """Contracts with many baja assets are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data[data['AssetCount'] > 2].copy()
        
        if anomalies.empty:
            return pd.DataFrame()
        
        anomalies['anomaly_type'] = 'Múltiples Assets en Baja'
        anomalies['anomaly_severity'] = 'Baja'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'bar',
                'x': 'AssetCount',
                'title': 'Distribución por Nº de Assets'
            }
        ]
