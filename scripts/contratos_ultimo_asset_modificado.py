"""
Script: Obtener Contratos por Último Asset Modificado

Extrae contratos basándose en el último asset modificado,
útil para identificar contratos con actividad reciente.
"""
import pandas as pd
from datetime import datetime, timedelta
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import CONTRACT_STATUS_MAP, ASSET_STATUS_MAP


@register_script
class ContratosUltimoAssetModificado(BaseScript):
    """
    Extrae contratos basándose en última modificación de assets.
    """
    
    name = "Contratos - Último Asset Modificado"
    description = "Contratos con assets modificados recientemente"
    category = "Extracción de datos"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for recently modified assets."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        # Last 30 days by default
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c,
                   acn_fld_Contract__r.ContractNumber,
                   acn_fld_Contract__r.Status,
                   acn_fld_Contract__r.NewCo_ServiceAccount__r.Name,
                   LastModifiedDate, CreatedDate,
                   acn_fld_StartDateVersion__c, acn_fld_EndDateVersion__c
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND LastModifiedDate >= LAST_N_DAYS:30
            AND acn_fld_Contract__c != null
            ORDER BY LastModifiedDate DESC
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets and group by contract."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Get last modified asset per contract
        df_sorted = df.sort_values('LastModifiedDate', ascending=False)
        df_unique = df_sorted.drop_duplicates(subset=['acn_fld_Contract__c'], keep='first')
        
        # Enrich with status labels
        df_unique['AssetStatusLabel'] = df_unique['Status'].map(ASSET_STATUS_MAP)
        df_unique['ContractStatusLabel'] = df_unique['acn_fld_Contract__r.Status'].map(CONTRACT_STATUS_MAP)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_unique))
        
        metrics.add_metric(
            'total_contracts',
            len(df_unique),
            'Contratos',
            '📋'
        )
        
        # Count by contract status
        if 'ContractStatusLabel' in df_unique.columns:
            status_counts = df_unique['ContractStatusLabel'].value_counts()
            for status, count in status_counts.head(3).items():
                if status:
                    metrics.add_metric(
                        f'status_{status[:10]}',
                        count,
                        str(status)[:15],
                        '📊'
                    )
        
        return ScriptResult(
            success=True,
            data=df_unique,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('acn_fld_Contract__r.ContractNumber', 'Contrato', ColumnType.TEXT),
            ColumnConfig('Name', 'Asset', ColumnType.TEXT),
            ColumnConfig('AssetStatusLabel', 'Estado Asset', ColumnType.STATUS),
            ColumnConfig('ContractStatusLabel', 'Estado Contrato', ColumnType.STATUS),
            ColumnConfig('LastModifiedDate', 'Última Modificación', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['AssetStatusLabel', 'ContractStatusLabel']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """No anomalies - this is extraction only."""
        return pd.DataFrame()
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'ContractStatusLabel',
                'title': 'Por Estado de Contrato'
            },
            {
                'type': 'pie',
                'names': 'AssetStatusLabel',
                'title': 'Por Estado de Asset'
            }
        ]
