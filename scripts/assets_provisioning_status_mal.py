"""
Script: Assets con Provisioning Status Incorrecto

Detecta assets con múltiples registros Active que indican
problemas de provisioning status mal configurado.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetsProvisioningStatusMal(BaseScript):
    """
    Detecta assets con provisioning status Active duplicados.
    """
    
    name = "Assets - Provisioning Status Incorrecto"
    description = "Detecta assets con duplicados Active por AssetReferenceId"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Estados a excluir (en curso, activos, etc)
    EXCLUDED_STATUSES = ['03', '11', '24', '27', '29', '02', '04', '08', '09']
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for assets and contracts."""
        limit_clause = "LIMIT 10000" if preview else ""
        
        # Query 1: Parent assets with provisioning info
        query_assets = f"""
            SELECT Id, Status, vlocity_cmt__ProvisioningStatus__c, 
                   acn_fld_Contract__c, vlocity_cmt__AssetReferenceId__c, 
                   vlocity_cmt__Action__c, NewCo_OriginContractType__c
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND vlocity_cmt__ProvisioningStatus__c = 'Active'
            {limit_clause}
        """
        
        return [query_assets]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find provisioning status anomalies."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Group by AssetReferenceId
        grouped = df.groupby('vlocity_cmt__AssetReferenceId__c').apply(
            lambda x: x.to_dict('records')
        ).to_dict()
        
        results = []
        
        for ref_id, assets in grouped.items():
            if not ref_id or len(assets) <= 1:
                continue
            
            # Check if there's at least one asset with Status '03'
            has_active_03 = any(a.get('Status') == '03' for a in assets)
            if not has_active_03:
                continue
            
            # Find assets that are NOT in excluded statuses
            for asset in assets:
                status = asset.get('Status', '')
                if status in self.EXCLUDED_STATUSES:
                    continue
                
                results.append({
                    'AssetId': asset.get('Id', ''),
                    'ContractId': asset.get('acn_fld_Contract__c', ''),
                    'AssetStatus': status,
                    'AssetStatusLabel': ASSET_STATUS_MAP.get(status, status),
                    'ProvisioningStatus': asset.get('vlocity_cmt__ProvisioningStatus__c', ''),
                    'AssetAction': asset.get('vlocity_cmt__Action__c', ''),
                    'OriginatingChannel': asset.get('NewCo_OriginContractType__c', ''),
                    'AssetReferenceId': ref_id,
                    'DuplicatesInGroup': len(assets)
                })
        
        df_result = pd.DataFrame(results)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'assets_affected',
            len(df_result),
            'Assets Afectados',
            '⚠️' if len(df_result) > 0 else '✅'
        )
        
        unique_refs = df_result['AssetReferenceId'].nunique() if not df_result.empty else 0
        metrics.add_metric(
            'unique_refs',
            unique_refs,
            'Referencias Afectadas',
            '📦'
        )
        
        return ScriptResult(
            success=True,
            data=df_result,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('AssetId', 'Asset ID', ColumnType.LINK),
            ColumnConfig('AssetStatusLabel', 'Estado Asset', ColumnType.STATUS),
            ColumnConfig('ProvisioningStatus', 'Provisioning', ColumnType.TEXT),
            ColumnConfig('AssetAction', 'Action', ColumnType.TEXT),
            ColumnConfig('DuplicatesInGroup', 'Duplicados', ColumnType.NUMBER),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['AssetStatusLabel', 'ProvisioningStatus', 'AssetAction']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All identified assets are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Provisioning Status Incorrecto'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'AssetStatusLabel',
                'title': 'Por Estado de Asset'
            },
            {
                'type': 'bar',
                'x': 'ProvisioningStatus',
                'title': 'Por Provisioning Status'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'fix_provisioning_status',
                'description': 'Corregir provisioning status a Inactive',
                'fields': {
                    'vlocity_cmt__ProvisioningStatus__c': 'Inactive'
                }
            }
        ]
