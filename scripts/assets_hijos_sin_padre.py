"""
Script: Assets Hijos sin Padre

Detecta assets hijos que quedaron huérfanos sin asociar al padre.
Estos aparecen incorrectamente en la página del contrato.

Condiciones de búsqueda:
- NewCo_ProductServiceCRMId__c = null
- acn_fld_Contract__c != null
- ParentId = null
- Product2.ProductCode != 'S0012'
- ProductFamily != 'Gas' y != 'Electricidad'

Para reparar, se asocian al asset padre sin hijos del mismo contrato.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetsHijosSinPadre(BaseScript):
    """
    Detecta y repara assets hijos sin padre asociado.
    """
    
    name = "Assets Hijos sin Padre"
    description = "Detecta assets hijos huérfanos sin asociar al padre"
    category = "Regularización"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for orphan child assets."""
        limit_clause = "LIMIT 1000" if preview else ""
        
        # Query 1: Assets hijos huérfanos
        query_orphans = f"""
            SELECT Id, Status, acn_fld_Contract__c, acn_fld_Contract__r.Status, 
                   Product2.Name, Product2.ProductCode, ParentId,
                   Parent.vlocity_cmt__RootItemId__c, vlocity_cmt__ParentItemId__c,  
                   vlocity_cmt__AssetReferenceId__c, vlocity_cmt__ProvisioningStatus__c, 
                   vlocity_cmt__Action__c, CreatedDate,
                   vlocity_cmt__OrderProductId__r.Order.vlocity_cmt__OriginatingChannel__c,
                   ProductFamily
            FROM Asset 
            WHERE NewCo_ProductServiceCRMId__c = null 
            AND acn_fld_Contract__c != null
            AND ParentId = null 
            AND Product2.ProductCode != 'S0012' 
            AND ProductFamily != 'Gas' 
            AND ProductFamily != 'Electricidad'
            {limit_clause}
        """
        
        return [query_orphans]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process orphan child assets."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('orphans_raw', df)
        
        # Enrich with status labels
        df['StatusLabel'] = df['Status'].map(ASSET_STATUS_MAP)
        
        # Group by contract
        contracts_with_orphans = df['acn_fld_Contract__c'].nunique()
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df))
        
        metrics.add_metric(
            'orphan_assets',
            len(df),
            'Assets Huérfanos',
            '🔴'
        )
        
        metrics.add_metric(
            'affected_contracts',
            contracts_with_orphans,
            'Contratos Afectados',
            '📋'
        )
        
        # Count by product family
        if 'ProductFamily' in df.columns:
            family_counts = df['ProductFamily'].value_counts()
            for family, count in family_counts.items():
                if family:
                    metrics.add_metric(
                        f'family_{family}',
                        count,
                        f'Familia: {family}',
                        '📦'
                    )
        
        return ScriptResult(
            success=True,
            data=df,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('Id', 'ID Asset', ColumnType.TEXT),
            ColumnConfig('Product2.Name', 'Producto', ColumnType.TEXT),
            ColumnConfig('Product2.ProductCode', 'Código', ColumnType.TEXT),
            ColumnConfig('StatusLabel', 'Estado', ColumnType.STATUS),
            ColumnConfig('acn_fld_Contract__c', 'Contrato', ColumnType.LINK),
            ColumnConfig('ProductFamily', 'Familia', ColumnType.TEXT),
            ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['acn_fld_Contract__c', 'ProductFamily', 'Product2.ProductCode', 'StatusLabel']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All orphan assets are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Asset Hijo sin Padre'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'ProductFamily',
                'title': 'Distribución por Familia'
            },
            {
                'type': 'bar',
                'x': 'Product2.ProductCode',
                'title': 'Assets por Código de Producto'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'associate_to_parent',
                'description': 'Asociar assets huérfanos a su padre correspondiente',
                'fields': {
                    'ParentId': '(ID del padre)',
                    'vlocity_cmt__ParentItemId__c': '(RootItemId del padre)',
                    'vlocity_cmt__RootItemId__c': '(RootItemId del padre)'
                }
            }
        ]
