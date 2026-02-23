"""
Script: Assets sin Directriz

Detecta assets que no tienen directriz asociada cuando deberían tenerla.
Preserva 100% de la lógica del notebook AssetsWithoutDirectriz.ipynb.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetsWithoutDirectriz(BaseScript):
    """
    Detecta assets sin directriz.
    Preserva la lógica exacta del notebook: filtra por NewCo_GenerarDirectriz__c.
    """
    
    name = "Assets sin Directriz"
    description = "Detecta assets que deberían tener directriz pero no la tienen"
    category = "Detección de inconsistencias"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True  # Permite regularizar via Apex
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets without directriz (LÓGICA EXACTA DEL NOTEBOOK)."""
        limit_clause = "LIMIT 2000" if preview else ""
        
        # QUERY EXACTA DEL NOTEBOOK - NO modificar filtros
        query = f"""
            SELECT Id, Name, Status, 
                   NewCo_Directriz__c, 
                   Product2.ProductCode,
                   Product2.NewCo_GenerarDirectriz__c,
                   vlocity_cmt__ParentItemId__c,
                   acn_fld_Contract__c,
                   acn_fld_Contract__r.ContractNumber,
                   acn_fld_Contract__r.acn_fld_BusinessDivision__c,
                   CreatedDate, CreatedBy.Name
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND NewCo_Directriz__c = null
            AND Product2.NewCo_GenerarDirectriz__c = true
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets without directriz."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        # Enrich with status labels
        df['StatusLabel'] = df['Status'].map(ASSET_STATUS_MAP)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df))
        
        metrics.add_metric(
            'assets_without_directriz',
            len(df),
            'Sin Directriz',
            '🔴' if len(df) > 0 else '✅'
        )
        
        # Count by business division
        if 'acn_fld_Contract__r.acn_fld_BusinessDivision__c' in df.columns:
            div_counts = df['acn_fld_Contract__r.acn_fld_BusinessDivision__c'].value_counts()
            for div, count in div_counts.items():
                if div:
                    metrics.add_metric(
                        f'div_{div}',
                        count,
                        f'División: {div}',
                        '📊'
                    )
        
        # Count by product code
        if 'Product2.ProductCode' in df.columns:
            prod_counts = df['Product2.ProductCode'].value_counts()
            for code, count in prod_counts.head(5).items():
                if code:
                    metrics.add_metric(
                        f'prod_{code}',
                        count,
                        f'Producto: {code}',
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
            ColumnConfig('Name', 'Asset', ColumnType.TEXT),
            ColumnConfig('Product2.ProductCode', 'Código Producto', ColumnType.TEXT),
            ColumnConfig('StatusLabel', 'Estado', ColumnType.STATUS),
            ColumnConfig('acn_fld_Contract__r.ContractNumber', 'Contrato', ColumnType.TEXT),
            ColumnConfig('acn_fld_Contract__r.acn_fld_BusinessDivision__c', 'División', ColumnType.TEXT),
            ColumnConfig('CreatedBy.Name', 'Creado Por', ColumnType.TEXT),
            ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations matching notebook Apex logic."""
        return [
            {
                'name': 'asignar_directriz',
                'description': 'Asignar Directriz + Precios (ejecuta NewCo_PricingHandler.handlerReintentoInformarPrecios)',
                'apex_method': 'NewCo_PricingHandler.handlerReintentoInformarPrecios',
                'apex_params': {
                    'object_type': 'Asset',
                    'regularize': True
                },
                'chunk_size': 1  # Como en notebook: 1 registro por llamada
            }
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['acn_fld_Contract__r.acn_fld_BusinessDivision__c', 'Product2.ProductCode']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All active assets without directriz are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Asset sin Directriz'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'acn_fld_Contract__r.acn_fld_BusinessDivision__c',
                'title': 'Por División de Negocio'
            },
            {
                'type': 'bar',
                'x': 'Product2.ProductCode',
                'title': 'Por Código de Producto'
            }
        ]
