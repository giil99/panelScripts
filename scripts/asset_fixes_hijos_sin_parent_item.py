"""
Script: Asset Fixes - Hijos sin ParentItemId

Detecta assets hijos que no tienen el campo vlocity_cmt__ParentItemId__c
pero sí tienen un parent asociado que necesita ser corregido.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetFixesHijosSinParentItem(BaseScript):
    """
    Detecta assets hijos sin ParentItemId pero con Parent asociado.
    """
    
    name = "Asset Fixes - Hijos sin ParentItemId"
    description = "Assets hijos que necesitan corrección de ParentItemId"
    category = "Regularización"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for child assets missing ParentItemId."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        # Query 1: Assets with Parent but no ParentItemId
        query = f"""
            SELECT Id, Name, Status, ParentId, 
                   vlocity_cmt__ParentItemId__c,
                   Parent.vlocity_cmt__RootItemId__c,
                   acn_fld_Contract__c,
                   acn_fld_Contract__r.ContractNumber,
                   CreatedDate, LastModifiedDate
            FROM Asset
            WHERE ParentId != null
            AND vlocity_cmt__ParentItemId__c = null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to identify those needing ParentItemId fix."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Add status labels
        df['AssetStatusLabel'] = df['Status'].map(ASSET_STATUS_MAP)
        
        # Check which can be fixed (have Parent.RootItemId)
        df['CanFix'] = df['Parent.vlocity_cmt__RootItemId__c'].notna()
        df['FixAction'] = df.apply(
            lambda x: 'Copiar RootItemId a ParentItemId' if x['CanFix'] else 'Verificar manualmente',
            axis=1
        )
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df))
        
        can_fix = df['CanFix'].sum()
        cannot_fix = len(df) - can_fix
        
        metrics.add_metric(
            'total_affected',
            len(df),
            'Assets Afectados',
            '⚠️' if len(df) > 0 else '✅'
        )
        
        metrics.add_metric(
            'can_auto_fix',
            can_fix,
            'Corrección Auto',
            '🔧'
        )
        
        metrics.add_metric(
            'manual_review',
            cannot_fix,
            'Revisión Manual',
            '👁️'
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
            ColumnConfig('AssetStatusLabel', 'Estado', ColumnType.STATUS),
            ColumnConfig('ParentId', 'Parent ID', ColumnType.LINK),
            ColumnConfig('CanFix', 'Corrección Auto', ColumnType.BOOLEAN),
            ColumnConfig('FixAction', 'Acción', ColumnType.TEXT),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['AssetStatusLabel', 'CanFix']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All assets without ParentItemId are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Sin ParentItemId'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'CanFix',
                'title': 'Por Tipo de Corrección'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'fix_parent_item_id',
                'description': 'Copiar Parent.RootItemId a ParentItemId',
                'fields': {
                    'vlocity_cmt__ParentItemId__c': '(Parent.vlocity_cmt__RootItemId__c)'
                }
            }
        ]
